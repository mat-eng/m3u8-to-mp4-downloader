"""
Created on 07.10.2023
@author: mat-eng
@description: generate executable
"""
########################################################################################################################
# Import libraries
import os
import shutil
import platform

########################################################################################################################
# Application version
app_name = "m3u8-to-mp4-downloader-"
app_version = "v001"

########################################################################################################################
if __name__ == "__main__":
    print("Starting compilation of main executable... Can take several minutes...")

    # Get os
    current_os = platform.system()

    if current_os == "Windows":
        app_extension = ".exe"
        bin_folder = "Windows/"
    elif current_os == "Darwin":
        app_extension = ""
        bin_folder = "MacOS/"
    else:
        app_extension = ""
        bin_folder = current_os + "/"

    app = app_name + app_version + app_extension

    # Build main exe file for windows
    os.system("pyinstaller m3u8-to-mp4-downloader.py  --clean --onefile --noconfirm --add-binary ffmpeg" + app_extension + ";ffmpeg")

    # Rename exe
    os.rename("./dist/m3u8-to-mp4-downloader" + app_extension, "./dist/" + app)

    # Move to bin folder
    shutil.move("./dist/" + app, "./bin/" + bin_folder)

    # Remove dist folder
    shutil.rmtree('./dist')

    # Remove folder created during exe generation
    shutil.rmtree('./build')

    # Remove file created during exe generation
    os.remove("./m3u8-to-mp4-downloader.spec")
