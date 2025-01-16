# Copyright 2021 Patrick C. Tapping
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Utility methods for image data processing.

If the (optional) `numba <http://numba.pydata.org/>`__ library is installed, some methods are able
to be accelerated using the numba just-in-time (JIT) compiler.
In the absence of the library, alternative numpy-based implementations are used.
The ``_np_`` and ``_nb_`` prefixes denote the numpy or numba implementations, respectively.
These should not be called directly, instead, use the non-prefixed version of the methods
documented here which will choose the appropriate implementation for you.
"""

__all__ = ["unpack_uint12", "fvb", "fvb_images", "decode_image_data", "decode_image_with_metadata", "decode_metadata", "FrameServer", "FrameDump"]

import logging
import threading
import struct
from time import monotonic, sleep

import numpy as np

from . error import *

_log = logging.getLogger(__name__)
"""Logging output for use by this module."""


# numpy routines for data processing, which will be used if the numba library is not available.
# These are generally slower than the numba compiled versions, but not too slow to use.
def _np_unpack_uint12(packed_data):
    """
    Unpacks the 12BitPacked image format into an array of unsigned 16-bit integers.

    `packed_data` is numpy array of ``np.uint8``, consisting of pairs of 12-bit numbers packed into 3 byte sequences.

    :param packed_data: Numpy array of ``np.uint8`` containing 12BitPacked image data.
    :returns: Image data as a numpy array of ``np.uint16``.
    """

    # This routine is written using numpy array operations, which is only about 5x slower than the compiled numba version.
    # This method generally shouldn't be called directly.
    # Instead, use unpack_uint12 which will select the numba or numpy versions as appropriate.

    # packed_data must be at least two values packed into 3 bytes
    if not packed_data.shape[0]%3 == 0:
        raise RuntimeError("Input data size must be a multiple of 3 bytes (pairs of 12-bit numbers packed into 3 bytes)")

    # Output array, 16-bit unsigned integers. Upper 4 bits will be zero.
    out = np.empty(2*(packed_data.shape[0]//3), dtype=np.uint16)

    # This looks simple but uses extra temporary data structures
    #out[0::2] = (packed_data[0::3].astype(np.uint16) << 4) + (packed_data[1::3].astype(np.uint16) & 0xF)
    #out[1::2] = (packed_data[2::3].astype(np.uint16) << 4) + (packed_data[1::3].astype(np.uint16) >> 4)

    # This looks uglier, but is 30% faster
    out[0::2] = packed_data[0::3]
    out[0::2] = out[0::2] << 4
    out[0::2] += packed_data[1::3] & 0xF

    out[1::2] = packed_data[2::3]
    out[1::2] = out[1::2] << 4
    out[1::2] += packed_data[1::3] >> 4

    return out
# Use numpy version by default
unpack_uint12 = _np_unpack_uint12


def _np_fvb(image):
    """
    Perform full-vertical-binning (FVB) of image data.

    ``image`` is a 2-dimensional numpy array of image data, where the first dimension indexes the
    column (width, x-coordinate) of the image, the second the row (height, y-coordinate).
    
    The vertically binned data will be returned as the mean as a 1-dimensional array of float32.

    :param image: Numpy array of image data.
    :returns: Vertically binned array of ``np.float32``.
    """

    # This numpy routine simply takes the mean across the second axis and is fast, but only single-threaded.
    # The numba version is faster due to parallelisation.
    # This method generally shouldn't be called directly.
    # Instead, use fvb which will select the numba or numpy versions as appropriate.

    return np.mean(image, axis=1).astype(np.float32)
# Use numpy version by default
fvb = _np_fvb

def _np_fvb_images(image):
    """
    Perform full-vertical-binning (FVB) of a set of image data.

    ``images`` is a 3-dimensional numpy array of image data in uint16 or uint32 format, where the
    first dimension indexes the image number, the second the column (width, x-coordinate) of the image, the third the row (height, y-coordinate).

    The vertically binned data will be returned as the mean as a 2-dimensional array of float32.

    :param image: Numpy array of image data in uint16 or uint32 format.
    :returns: Vertically binned array of ``np.float32``.
    """
    return np.mean(image, axis=2).astype(np.float32)
# Use numpy version by default
fvb_images = _np_fvb_images


# Use numba accelerated routines if available
try:
    import numba as nb
    
    @nb.njit(nb.uint16[::1](nb.uint8[::1]), fastmath=True, parallel=True)
    def _nb_unpack_uint12(packed_data):
        """
        Unpacks the 12BitPacked image format into an array of unsigned 16-bit integers.

        `packed_data` is numpy array of ``np.uint8``, consisting of pairs of 12-bit numbers packed into 3 byte sequences.

        :param packed_data: Numpy array of ``np.uint8`` containing 12BitPacked image data.
        :returns: Image data as a numpy array of ``np.uint16``.
        """

        # This routine is written in a very simplistic manner which the numba just-in-time (JIT) compiler is easily able to optimize.
        # Running this as pure python code is not advisable! Tests indicate it is about 6500x slower than the compiled version.
        # In case the numba library is unavailable, a numpy routine will be used instead, which is only about 5x slower.
        # This method generally shouldn't be called directly.
        # Instead, use unpack_uint12 which will select the numba or numpy versions as appropriate.

        # packed_data must be at least two values packed into 3 bytes
        if not packed_data.shape[0]%3 == 0:
            raise RuntimeError("Input data size must be a multiple of 3 bytes (pairs of 12-bit numbers packed into 3 bytes)")

        # Output array, 16-bit unsigned integers. Upper 4 bits will be zero.
        out = np.empty(2*(packed_data.shape[0]//3), dtype=np.uint16)

        for i in nb.prange(packed_data.shape[0]//3):
            byte1 = np.uint16(packed_data[i*3])
            byte2 = np.uint16(packed_data[i*3 + 1])
            byte3 = np.uint16(packed_data[i*3 + 2])
            out[2*i]     = (byte1 << 4) + (byte2 & 0xF)
            out[2*i + 1] = (byte3 << 4) + (byte2 >> 4)

        return out
    # Override with numba version
    unpack_uint12 = _nb_unpack_uint12


    @nb.njit([nb.float32[:](nb.uint16[:,:]), nb.float32[:](nb.uint32[:,:])], parallel=True)
    def _nb_fvb(image):
        """
        Perform full-vertical-binning (FVB) of image data.

        ``image`` is a 2-dimensional numpy array of image data in uint16 or uint32 format, where the
        first dimension indexes the column (width, x-coordinate) of the image, the second the row (height, y-coordinate).
        
        The vertically binned data will be returned as the mean as a 1-dimensional array of float32.

        :param image: Numpy array of image data in uint16 or uint32 format.
        :returns: Vertically binned array of ``np.float32``.
        """

        # This numba accelerated routine is not intrinsically faster than the numpy version on a single CPU core,
        # but is faster because of parallelisation.
        # This method generally shouldn't be called directly.
        # Instead, use :meth:`fvb` which will select the numba or numpy versions as appropriate.

        result = np.zeros((image.shape[0],), dtype=np.uint64)
        for col in nb.prange(image.shape[0]):
            for row in nb.prange(image.shape[1]):
                result[col] += image[col,row]
        return (result/image.shape[1]).astype(np.float32)
    # Override with numba version
    fvb = _nb_fvb

    @nb.njit([nb.float32[:,:](nb.uint16[:,:,:]), nb.float32[:,:](nb.uint32[:,:,:])], parallel=True)
    def _nb_fvb_images(images):
        """
        Perform full-vertical-binning (FVB) of a set of image data.

        ``images`` is a 3-dimensional numpy array of image data in uint16 or uint32 format, where the
        first dimension indexes the image number, the second the column (width, x-coordinate) of the image, the third the row (height, y-coordinate).

        The vertically binned data will be returned as the mean as a 2-dimensional array of float32.

        :param image: Numpy array of image data in uint16 or uint32 format.
        :returns: Vertically binned array of ``np.float32``.
        """
        # This tends to outperform the numpy version in certain circumstances
        # It would typically be used when n is large.
        result = np.zeros((images.shape[0], images.shape[1]), dtype=np.uint64)
        for n in nb.prange(images.shape[0]):
            for col in nb.prange(images.shape[1]):
                for row in nb.prange(images.shape[2]):
                    result[n,col] += images[n,col,row]
        return (result/images.shape[2]).astype(np.float32)
    # Override with numba version
    fvb_images = _nb_fvb_images

except:
    _log.warning("The numba library is not available. Pure numpy routines will be used instead but performance may suffer.")


def decode_image_data(data_raw, encoding, width, height, stride):
    """
    Decode raw bytes into an image.

    The decoding process needs to know the ``encoding`` of the data, which should be one of
    ``"Mono12"``, ``"Mono12Packed"``, ``"Mono16"``, or ``"Mono32"``.

    The ``height`` and ``width`` parameters determine the shape of the returned image data in
    pixels. There may be redundant padding bytes at the end of rows of pixels, in which case the
    ``stride`` parameter (in bytes) may be larger than expected given the width and bit-depth of the
    image. Additionally, padding at the end of the image data may be optionally be present, which is
    used by the Andor subsystem to align the data to 8-byte boundaries.

    If metadata is enabled and present in ``data_raw`` it will be ignored. To preserve information
    in the metadata, see the :meth:`decode_image_with_metadata` function.

    :param data_raw: Raw image byte data.
    :param encoding: String describing the image encoding method.
    :param width: Width of the resulting image, in pixels.
    :param height: Height of the resulting image, in pixels.
    :param stride: Number of bytes used to encode a single row of pixels.

    :returns: Image as 2D numpy array with shape (width, height).
    """
    # Expect data_raw to always be uint8 direct from waitBuffer calls.
    if not data_raw.dtype == np.uint8:
        raise RuntimeError("Image decoding requires data_raw to be array of uint8 data type.")

    # Trim off padding and metadata
    data_raw = data_raw[0:stride*height]

    # Convert to correct data type, convert stride from bytes to array elements
    if encoding in ("Mono12", "Mono16"):
        # Interpret data as uint16 type (no copy)
        data = data_raw.view(dtype=np.uint16)
        stride = stride//2
    elif encoding == "Mono12Packed":
        # Unpack Mono12Packed into uint16 type (data copy required)
        data = unpack_uint12(data_raw)
        # Stride so should be 1.5x larger now
        stride = 3*stride//2
    elif encoding == "Mono32":
        # Interpret data as uint32 type (no copy)
        data = data_raw.view(dtype=np.uint32)
        stride = stride//4
    else:
        raise RuntimeError(f"Pixel encoding type '{encoding}' not supported, (must be Mono12, Mono12Packed, or Mono32).")
    
    # Reshape from 1D to a 2D array, will still include padding
    data = data.reshape((stride, height), order="F")
    # Slice data array to remove any padding pixels at end of rows
    data = data[0:width,:]

    return data


def decode_image_with_metadata(data_raw):
    """
    Decode raw bytes into an image, using the included frame info and timestamp metadata.

    A tuple of the decoded image (as 2D numpy array) and timestamp (in clock ticks) will be
    returned.

    Note that this function may be useless, as it is not clear that any camera supports the
    ``MetadataFrameInfo`` property, and thus there may never be the metadata required to determine
    the image dimensions etc.

    :param data_raw: Raw byte data containing image and metadata.
    :returns: Image and metadata timestamp.
    """
    md, imagedata = decode_metadata(data_raw)
    image = decode_image_data(imagedata, md["encoding"], md["width"], md["height"], md["stride"])
    return image, md["timestamp"]


def decode_metadata(metadata_raw):
    """
    Decode a frame metadata block.

    If metadata is enabled for image frames, then the image data contains additional fields appended
    to the pixel data. The information is contained in three different block types:

    - FrameInfo (16 bytes) Height (uint16), width (uint16), [unused] (byte), encoding (uint8),
        stride (uint16), chunk_id=7 (uint32), chunk_length (uint32).
    - Ticks (16 bytes) Ticks (uint64), chunk_id=1 (uint32), chunk_length (uint32).
    - FrameData (variable size) Image (stride × height + padding bytes), chunkid=0 (uint32),
        chunk_length (uint32).

    Values are stored as little-endian. The values of chunk_length do not include the length field
    itself, so are 4-bytes less than the actual chunk size.

    The timestamp is stored as clock ticks since the camera startup. The frequency of the camera
    clock (in Hz) can be obtained using the ``TimeStampClockFrequency`` property.

    This function should be able to handle the image data being missing, in the case where the image
    data has been split from the appended metadata. If the image data is missing, ``None`` will be
    returned in place of the image data.

    The returned dictionary of metadata will have the fields ``height``, ``width``, ``stride``,
    ``encoding`` (as string), and ``timestamp``. The image data will be the raw byte stream as a
    numpy array of size (stride × height + padding bytes). The fields will only be present in the
    dictionary if the relevant blocks have been enabled, for example, buy settings the ``Metadata``
    and ``MetadataTimestamp`` properties to ``True``.

    Note that the ``MetadataFrameInfo`` property and data block format is documented in the metadata
    section of the Andor SDK3 documentation, but is not actually listed as a valid feature for any
    camera model. The Zyla used for testing did not implement ``MetadataFrameInfo``, but the
    decoding of the FrameInfo block should work if a camera happens to support it.

    :param metadata_raw: Image data containing metadata.
    :returns: Tuple of dictionary of metadata and bytes of raw image data.
    """
    metadata = {}
    imagedata = None
    # Start at end of byte stream and work backwards
    p = len(metadata_raw)
    while p >= 8:
        # Read chunk id and length
        p -= 8
        chunk_id, chunk_length = struct.unpack_from("<LL", metadata_raw, offset=p)
        if chunk_id not in (0, 1, 7):
            raise RuntimeError(f"Chunk id={chunk_id} not recognised")
        # Read chunk data block
        p -= chunk_length - 4
        if p < 0:
            # Pointer has gone beyond the start of the byte stream
            if chunk_id == 0:
                # Allow for the image data to be empty, still decode metadata if present
                break
            raise RuntimeError(f"Not enough data to decode chunk id={chunk_id}, length={chunk_length}")
        if chunk_id == 7:
            # FrameInfo chunk
            if not chunk_length == 12:
                raise RuntimeError("FrameInfo chunk (id=7) must have length=12")
            metadata["height"], metadata["width"], encoding, metadata["stride"] = struct.unpack_from("<HHxBH", metadata_raw, offset=p)
            if 0 <= encoding <= 3:
                metadata["encoding"] = ["Mono16", "Mono12", "Mono12Packed", "Mono32"][encoding]
            else:
                metadata["encoding"] = "Unknown"
        elif chunk_id == 1:
            # Ticks chunk
            if not chunk_length == 12:
                raise RuntimeError("Ticks chunk (id=1) must have length=12")
            metadata["timestamp"] = struct.unpack_from("<Q", metadata_raw, offset=p)[0]
        elif chunk_id == 0:
            # FrameData chunk
            if imagedata:
                raise RuntimeError("Duplicate FrameData chunk found")
            if chunk_length < 1:
                raise RuntimeError("FrameData chunk has zero length")
            imagedata = np.array(metadata_raw[p:p + chunk_length - 4], dtype=np.uint8)
            # still raw bytes, could contain padding
    return metadata, imagedata
            

class FrameServer():
    """
    Class which can start an acquisition, then serve each frame to a given function.

    The frame callback method should take the form of ``frame_callback(n, data, timestamp)``,
    where ``n`` is the frame number (zero-based) in the acquisition series, ``data`` is the
    image data, and timestamp is the metadata timestamp if metadata is enabled, else zero.
    
    The optional completion callback method should take the form of ``completion_callback(n)``,
    where ``n`` is the number of frames which were acquired.

    If ``fvb=True``, then the data provided to the callback method is a 1-dimensional numpy array.
    Otherwise, the data is a 2-dimensional numpy array with axes (row, column).

    The rate that frames are served can be limited using the ``frame_rate_max`` parameter.
    A value of zero or ``None`` will not restrict the frame rate. Note that this is the rate
    of frames served, not the actual acquisition rate.

    :param cam: :class:`~andor3.andor3.Andor3` camera to use for frame acquisition.
    :param frame_callback: Function to call on each frame acquisition event.
    :param completion_callback: Function to call when acquisition is completed.
    :param fvb: Perform full-vertical-binning on the image data.
    :param frame_rate_max: Maximum frame serving rate in frames per second.
    """
    def __init__(self, cam, frame_callback, completion_callback=None, fvb=False, frame_rate_max=None):
        self._cam = cam
        self._thread = None
        self._thread_stop = threading.Event()
        if callable(frame_callback):
            self._frame_callback = frame_callback
        else:
            raise TypeError("FrameServer completion_callback parameter is not a callable function.")
        if callable(completion_callback):
            self._completion_callback = completion_callback
        else:
            if completion_callback is not None:
                _log.warning("FrameServer completion_callback parameter is not a callable function, ignoring.")
            self._completion_callback = None
        self._fvb = bool(fvb)
        self._frame_interval = 1.0/frame_rate_max if frame_rate_max else 0.0

    def start(self, nbuffers=10, fvb=None, frame_rate_max=None):
        """
        Start the camera and begin serving acquired frames.

        A circular series of ``nbuffers`` buffers are used, and the returned image data may be only
        a view of the raw camera buffer memory (not copied). If the image data is to be retained for
        long periods, it should be copied into its own memory, either indirectly by a mathematical
        operation or explicitly by something like ``img = data.copy()``. If the ``fvb=True`` option
        is used, the served data is computed from the buffer and so this is not an issue.

        Full-vertical binning can be enabled by setting ``fvb=True``.

        The rate that frames are served can be limited using the ``frame_rate_max`` parameter.
        A value of zero or ``None`` will not restrict the frame rate. Note that this is the rate
        of frames served, not the actual acquisition rate.

        :param nbuffers: Number of frames in the circular image buffer.
        :param fvb: Perform full-vertical-binning on the image data.
        :param frame_rate_max: Maximum acquisition rate in frames per second.
        """
        self._cam.queueBuffer(nbuffers)
        if fvb is not None:
            self._fvb = bool(fvb)
        if frame_rate_max is not None:
            self._frame_interval = 1.0/frame_rate_max if frame_rate_max else 0.0
        self._thread_stop.clear()
        self._thread = threading.Thread(target=self._run, name="Andor3_FrameServer", daemon=True)
        self._thread.start()

    def stop(self):
        """
        Stop the FrameServer.
        """
        self._thread_stop.set()
        # Wait for thread to finish
        if self._thread and self._thread.is_alive() and not self._thread == threading.current_thread():
            self._thread.join()

    def _run(self):
        """
        Run the acquisition thread.
        """
        frame_count = 0
        self._cam.CycleMode = "Continuous"
        last_frame_time = 0.0
        self._cam.start()
        while (not self._thread_stop.is_set()) and self._cam.CameraAcquiring:
            # Requeue to use as a circular buffer
            try:
                data = self._cam.waitBuffer(timeout=200, copy=False, requeue=True)
            except AndorError as ex:
                if ex.code == AT_ERR.TIMEDOUT:
                    # Ignore timeout errors
                    continue
                elif ex.code == AT_ERR.NODATA:
                    # Something nondescript went wrong
                    break
                else:
                    raise
            # Rate limit the frame serving if a maximum frame rate was specified
            if self._frame_interval:
                this_frame_time = monotonic()
                if this_frame_time < last_frame_time + self._frame_interval:
                    continue
            # Notify listener a frame has been acquired
            img, timestamp = self._cam.decode_image(data)
            if self._fvb:
                img = fvb(img)
            self._frame_callback(frame_count, img, timestamp)
            frame_count += 1
            if self._frame_interval:
                last_frame_time = monotonic()
        # Stop the acquisition if it isn't already
        self._cam.stop()
        # Notify listener the acquisition is completed
        if self._completion_callback is not None:
            self._completion_callback(frame_count)
        self._thread = None


class FrameDump():
    """
    Class which can start an acquisition, then notify on the conclusion of the acquisition event
    with all the acquired data.

    This acquisition style pre-allocates all memory for the frame data and thus can use a large
    amount of RAM. Ensure your system has the available RAM for the number and size of images you
    wish to acquire.

    The callback method should take the form of ``completion_callback(data, timestamps)``,
    where ``data`` is a numpy array of the image data, and timestamps is a numpy array of
    timestamps for the data if metadata is enabled (zeros otherwise).

    If ``fvb=True``, then the data provided to the callback method is a 2-dimensional numpy array,
    with axes being (n, column). Otherwise, the data is a 3-dimensional numpy array with axes (n,
    row, column).

    :param cam: :class:`~andor3.andor3.Andor3` camera to use for frame acquisition.
    :param completion_callback: Function to call when acquisition is completion.
    :param fvb: Perform full-vertical-binning on the image data.
    """

    def __init__(self, cam, completion_callback, fvb=False):
        self._cam = cam
        self._thread = None
        self._thread_stop = threading.Event()
        if callable(completion_callback):
            self._completion_callback = completion_callback
        else:
            raise TypeError("FrameDump completion_callback parameter is not a callable function.")
        self._fvb = bool(fvb)

    def start(self, n_images=None, fvb=None):
        """
        Start the acquisition process.

        A maximum of ``n_images`` frames will be acquired. If set to ``None`` (default), the number
        of images will be determined by the camera's ``FrameCount`` and ``AccumulateCount``
        properties.

        Full-vertical binning can be enabled or disabled using the ``fvb`` parameter.

        :param n_images: Maximum number of images to capture.
        :param fvb: Perform full-vertical-binning on the image data.
        """
        # TODO: Should check here for supported pixel format etc
        self._cam.CycleMode = "Fixed"
        if n_images:
            self._cam.FrameCount = int(n_images)*self._cam.AccumulateCount
        else:
            n_images = self._cam.FrameCount//self._cam.AccumulateCount
        self._cam.queueBuffer(n_images)
        if fvb is not None:
            self._fvb = bool(fvb)
        self._thread_stop.clear()
        self._thread = threading.Thread(target=self._run, args=(n_images,), name="Andor3_FrameDump", daemon=True)
        self._thread.start()

    def stop(self):
        """
        Stop the camera.
        """
        self._thread_stop.set()
        # Wait for thread to finish
        if self._thread and self._thread.is_alive() and not self._thread == threading.current_thread():
            self._thread.join() 

    def _run(self, frame_count_max):
        # Camera does not automatically stop acquiring once FrameCount has been reached???
        frame_count = 0
        self._cam.start()
        while (not self._thread_stop.is_set()) and (frame_count < frame_count_max) and self._cam.CameraAcquiring:
            try:
                # Do we really have to do this? Can't the camera just fill the buffers itself?
                self._cam.waitBuffer(timeout=250)
            except AndorError as ex:
                if ex.code == AT_ERR.TIMEDOUT:
                    # Ignore timeout errors
                    continue
                elif ex.code == AT_ERR.NODATA:
                    # Something nondescript went wrong
                    break
                else:
                    raise
            frame_count += 1
        # Stop the acquisition if it isn't already
        self._cam.stop()
        
        # Process the raw byte data to extract the images
        encoding = self._cam._image_properties["encoding"] # string
        imgsize = self._cam._image_properties["size"] # bytes, including metadata
        postpad = (8 - imgsize%8)%8                   # bytes, for 8-byte alignment
        w = self._cam._image_properties["width"]      # pixels
        s = self._cam._image_properties["stride"]     # bytes
        h = self._cam._image_properties["height"]     # pixels
        count = self._cam._image_buffer.shape[0]//imgsize
        n = min(count, frame_count)                    
        # View the buffer as separate byte blocks for each image
        buffer = self._cam._image_buffer.reshape((count, imgsize + postpad))[:,:imgsize]
        # Metadata may be present at end of each image data block
        metadata_raw = buffer[:,s*h:]
        timestamps = np.zeros(metadata_raw.shape[0], dtype=np.uint64)
        if metadata_raw.shape[1] > 0:
            try:
                for i, md in enumerate(metadata_raw):
                    timestamps[i] = decode_metadata(md)[0]["timestamp"]
            except: pass
        if encoding == "Mono12Packed":
            # For 12-bit images, we have to allocate a larger buffer to unpack into
            # This means a (temporary) huge increase in RAM use...
            images = np.empty((count, (3*s//2)*h), dtype=np.uint16)
            for i in range(images.shape[0]):
                images[i] = unpack_uint12(buffer[i])
            # Updated stride value (in bytes) is 1.5x larger now
            s = 3*s//2
            images = images.reshape((count, h, s)).view(dtype=np.uint16)[:n,:,:w]
        else:
            # For 16 or 32 bit images, we should be able to decode image data in place
            # Reinterpret buffer as new data type, crop off metadata, reshape to image dimensions
            if encoding == "Mono32":
                images = buffer.view(dtype=np.uint32)[:,:h*s//4].reshape((count, h, s//4))[:n,:,:w]
            else:
                images = buffer.view(dtype=np.uint16)[:,:h*s//2].reshape((count, h, s//2))[:n,:,:w] 
        # Swap axes to (count, width, height)
        images = np.swapaxes(images, 1, 2)
        # Perform vertical binning if requested
        # TODO: There's probably a less RAM-hungry method to do this
        if self._fvb:
            images = fvb_images(images)
        # The buffer may still be referenced (as "images"), but we still want to get it garbage collected ASAP...
        self._cam.flush()
        # Notify that acquisition has completed
        self._completion_callback(images, timestamps)
        self._thread = None 
     


