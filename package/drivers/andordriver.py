import numpy as np
import os
from package.drivers.andor_sdk.atcore import ATCore, ATCoreException
from package.drivers.jkamgendriver import JKamGenDriver

os.environ['PATH'] = os.path.dirname(__file__) + os.sep + 'andor_sdk' + ';' + os.environ['PATH']


class AndorDriver(JKamGenDriver):
    def _open_connection(self):
        self.sdk3 = ATCore()
        print('Connected to Andor driver')

    def _close_connection(self):
        pass

    def _get_serial_number(self, cam):
        return self.sdk3.get_string(cam, 'SerialNumber')

    def _arm_camera(self, serial_number):
        cam = self.sdk3.open(0)
        if self._get_serial_number(cam) == serial_number:
            return cam
        else:
            print(f'Andor camera with serial number: {serial_number} not found!')
            return None

    def _disarm_camera(self, cam):
        self.sdk3.flush(cam)
        self.sdk3.close(cam)

    def _start_acquisition(self, cam):
        self.sdk3.flush(cam)
        self.sdk3.command(cam, 'AcquisitionStart')

    def _stop_acquisition(self, cam):
        self.sdk3.command(cam, 'AcquisitionStop')
        self.sdk3.flush(cam)

    def _set_exposure_time(self, cam, exposure_time):
        """
        exposure time input in ms. Andor SDK3 sets exposure time in s and gets it in us.
        Return actual exposure time in ms
        """
        converted_exposure_time = exposure_time * 1e-3
        self.sdk3.set_float(cam, 'ExposureTime', converted_exposure_time)
        exposure_time_result = self.sdk3.get_float(cam, 'ExposureTime') * 1e3
        return exposure_time_result

    def _trigger_on(self, cam):
        pass

    def _trigger_off(self, cam):
        self._set_software_trigger(cam)

    def _set_hardware_trigger(self, cam):
        self.sdk3.set_enum_string(cam, 'TriggerMode', 'External')

    def _set_software_trigger(self, cam):
        self.sdk3.set_enum_string(cam, 'TriggerMo'
                                       'de', 'Software')

    def _execute_software_trigger(self, cam):
        self.sdk3.command(cam, 'SoftwareTrigger')

    def _grab_frame(self, cam):
        self.sdk3.queue_buffer(cam, self.buf.ctypes.data, self.imageSizeBytes)
        if not self._trigger_enabled:
            self._execute_software_trigger(cam)
        try:
            _, _ = self.sdk3.wait_buffer(cam, timeout=ATCore.AT_INFINITE)
        except ATCoreException:
            return
        np_arr = self.buf[0:self.config['aoiheight'] * self.config['aoistride']]
        np_d = np_arr.view(dtype='H')
        np_d = np_d.reshape(self.config['aoiheight'], round(np_d.size / self.config['aoiheight']))
        formatted_img = np_d[0:self.config['aoiheight'], 0:self.config['aoiwidth']]
        frame = np.copy(formatted_img.astype(int))
        return frame

    def _load_default_settings(self, cam):
        self.sdk3.set_enum_string(cam, "SimplePreAmpGainControl", "12-bit (low noise)")
        self.sdk3.set_enum_string(cam, "PixelEncoding", "Mono12")
        # self.system.set_enum_string(cam, "SimplePreAmpGainControl", "16-bit (low noise & high well capacity)")
        # self.system.set_enum_string(cam, "PixelEncoding", "Mono16")

        '''
        I believe AOI uses row major format for specifying width, height, left and top.
        '''
        # aoi_width = 40
        # aoi_height = 400
        # aoi_left = 830
        # aoi_top = 980
        # aoi_width = 1800
        # aoi_height = 1800
        # aoi_left = 200
        # aoi_top = 200
        # aoi_width = 40
        # aoi_height = 80
        # aoi_left = 840
        # aoi_top = 970
        '''
        I believe AOI uses row major format for specifying width, height, left and top.
        '''
        ####################################################################
        # aoi_width = 50
        # aoi_height = 650
        # aoi_left = 820
        # aoi_top = 820
        # self.sdk3.set_int(cam, "AOIWidth", aoi_width)
        # self.sdk3.set_int(cam, "AOIHeight", aoi_height)
        # self.sdk3.set_int(cam, "AOILeft", aoi_left)
        # self.sdk3.set_int(cam, "AOITop", aoi_top)
        # self.frame_dict['metadata']['AOIWidth']= aoi_width
        # self.frame_dict['metadata']['AOIHeight']= aoi_height
        # self.frame_dict['metadata']['AOILeft']= aoi_left
        # self.frame_dict['metadata']['AOITop']= aoi_top

        ####################################################################
        # New AOI for horizontal tweezers
        # aoi_width = 900
        # aoi_height = 300
        # aoi_left = 350
        # aoi_top = 1050
        # self.sdk3.set_int(cam, "AOIWidth", aoi_width)
        # self.sdk3.set_int(cam, "AOIHeight", aoi_height)
        # self.sdk3.set_int(cam, "AOILeft", aoi_left)
        # self.sdk3.set_int(cam, "AOITop", aoi_top)
        # self.frame_dict['metadata']['AOIWidth'] = aoi_width
        # self.frame_dict['metadata']['AOIHeight'] = aoi_height
        # self.frame_dict['metadata']['AOILeft'] = aoi_left
        # self.frame_dict['metadata']['AOITop'] = aoi_top

        ################################# New AOI for horizontal tweezers smaller ROI 06/01/2024
        aoi_width = 1100
        aoi_height = 80
        aoi_left = 350
        aoi_top = 1160
        self.sdk3.set_int(cam, "AOIWidth", aoi_width)
        self.sdk3.set_int(cam, "AOIHeight", aoi_height)
        self.sdk3.set_int(cam, "AOILeft", aoi_left)
        self.sdk3.set_int(cam, "AOITop", aoi_top)
        self.frame_dict['metadata']['AOIWidth'] = aoi_width
        self.frame_dict['metadata']['AOIHeight'] = aoi_height
        self.frame_dict['metadata']['AOILeft'] = aoi_left
        self.frame_dict['metadata']['AOITop'] = aoi_top

        ################################# Test ROI 07/01/2024
        # aoi_width = 1100
        # aoi_height = 400
        # aoi_left = 350
        # aoi_top = 1000
        # self.sdk3.set_int(cam, "AOIWidth", aoi_width)
        # self.sdk3.set_int(cam, "AOIHeight", aoi_height)
        # self.sdk3.set_int(cam, "AOILeft", aoi_left)
        # self.sdk3.set_int(cam, "AOITop", aoi_top)
        # self.frame_dict['metadata']['AOIWidth'] = aoi_width
        # self.frame_dict['metadata']['AOIHeight'] = aoi_height
        # self.frame_dict['metadata']['AOILeft'] = aoi_left
        # self.frame_dict['metadata']['AOITop'] = aoi_top

        ########################################################### new for debugging tweezers
        # aoi_width = 1100
        # aoi_height = 300
        # aoi_left = 350
        # aoi_top = 1100
        # self.sdk3.set_int(cam, "AOIWidth", aoi_width)
        # self.sdk3.set_int(cam, "AOIHeight", aoi_height)
        # self.sdk3.set_int(cam, "AOILeft", aoi_left)
        # self.sdk3.set_int(cam, "AOITop", aoi_top)
        # self.frame_dict['metadata']['AOIWidth'] = aoi_width
        # self.frame_dict['metadata']['AOIHeight'] = aoi_height
        # self.frame_dict['metadata']['AOILeft'] = aoi_left
        # self.frame_dict['metadata']['AOITop'] = aoi_top
        ###########################################################
        # aoi_width = 200
        # aoi_height = 650
        # aoi_left = 745
        # aoi_top = 820
        # self.sdk3.set_int(cam, "AOIWidth", aoi_width)
        # self.sdk3.set_int(cam, "AOIHeight", aoi_height)
        # self.sdk3.set_int(cam, "AOILeft", aoi_left)
        # self.sdk3.set_int(cam, "AOITop", aoi_top)
        # self.frame_dict['metadata']['AOIWidth'] = aoi_width
        # self.frame_dict['metadata']['AOIHeight'] = aoi_height
        # self.frame_dict['metadata']['AOILeft'] = aoi_left
        # self.frame_dict['metadata']['AOITop'] = aoi_top

        '''
        I believe AOI uses row major format for specifying width, height, left and top.
        '''
        # # 107-116MHz
        # aoi_width = 50
        # aoi_height = 350
        # aoi_left = 1040
        # aoi_top = 900
        # self.sdk3.set_int(cam, "AOIWidth", aoi_width)
        # self.sdk3.set_int(cam, "AOIHeight", aoi_height)
        # self.sdk3.set_int(cam, "AOILeft", aoi_left)
        # self.sdk3.set_int(cam, "AOITop", aoi_top)
        # self.frame_dict['metadata']['AOIWidth'] = aoi_width
        # self.frame_dict['metadata']['AOIHeight'] = aoi_height
        # self.frame_dict['metadata']['AOILeft'] = aoi_left
        # self.frame_dict['metadata']['AOITop'] = aoi_top



        # 98-120MHz
        # aoi_width = 70
        # aoi_height = 650
        # aoi_left = 1030
        # aoi_top = 680
        # self.sdk3.set_int(cam, "AOIWidth", aoi_width)
        # self.sdk3.set_int(cam, "AOIHeight", aoi_height)
        # self.sdk3.set_int(cam, "AOILeft", aoi_left)
        # self.sdk3.set_int(cam, "AOITop", aoi_top)
        # self.frame_dict['metadata']['AOIWidth'] = aoi_width
        # self.frame_dict['metadata']['AOIHeight'] = aoi_height
        # self.frame_dict['metadata']['AOILeft'] = aoi_left
        # self.frame_dict['metadata']['AOITop'] = aoi_top
        # 98-120MHz
        # aoi_width = 70
        # aoi_height = 650
        # aoi_left = 1190
        # aoi_top = 900
        # self.sdk3.set_int(cam, "AOIWidth", aoi_width)
        # self.sdk3.set_int(cam, "AOIHeight", aoi_height)
        # self.sdk3.set_int(cam, "AOILeft", aoi_left)
        # self.sdk3.set_int(cam, "AOITop", aoi_top)
        # self.frame_dict['metadata']['AOIWidth'] = aoi_width
        # self.frame_dict['metadata']['AOIHeight'] = aoi_height
        # self.frame_dict['metadata']['AOILeft'] = aoi_left
        # self.frame_dict['metadata']['AOITop'] = aoi_top

        # self.sdk3.set_int(cam, "AOI")
        # self.sdk3.set_enum_string(cam, "AOIBinning", "8x8")
        # self.sdk3.set_enum_string(cam, "AOIBinning", "4x4")
        self.sdk3.set_enum_string(cam, "AOIBinning", "1x1")
        #
        self.sdk3.set_enum_string(cam, 'CycleMode', 'Continuous')

        # self.sdk3.set_bool(cam, 'SensorCooling', True)
        self.sdk3.set_bool(cam, 'SensorCooling', False)
        self.sdk3.set_bool(cam, 'SpuriousNoiseFilter', False)

        '''
        Critical for timing, see Zyla manual 2.6.2.10 on Rolling Shutter Global Clear
        '''
        self.sdk3.set_bool(cam, 'RollingShutterGlobalClear', True)

        self.sdk3.set_enum_string(cam, 'PixelReadoutRate', '270 MHz')
        self.sdk3.set_enum_string(cam, "AuxiliaryOutSource", 'FireAny')

        self.imageSizeBytes = self.sdk3.get_int(cam, "ImageSizeBytes")
        print("    Queuing Buffer (size", self.imageSizeBytes, ")")
        self.buf = np.empty((self.imageSizeBytes,), dtype='B')

        self.config = {'aoiheight': self.sdk3.get_int(cam, "AOIHeight"),
                       'aoiwidth': self.sdk3.get_int(cam, "AOIWidth"),
                       'aoistride': self.sdk3.get_int(cam, "AOIStride"),
                       'pixelencoding': self.sdk3.get_enum_string(cam, "PixelEncoding")}
