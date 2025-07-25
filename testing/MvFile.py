import os

def move_old_files(src_folder, dest_folder, num_files_to_move=6, trigger_file_count=10):
    files = [f for f in os.listdir(src_folder) if os.path.isfile(os.path.join(src_folder, f))]
    print(len(files))
    if len(files) >= trigger_file_count:
        if not os.path.exists(dest_folder):
            os.makedirs(dest_folder)
        files.sort(key=lambda x: os.path.getmtime(os.path.join(src_folder, x)))
        for file in files[:num_files_to_move]:
            src_file = os.path.join(src_folder, file)
            dest_file = os.path.join(dest_folder, file)
            os.rename(src_file, dest_file)
        print(f'Moved files from: {src_folder} to {dest_folder}')
