docstr = """
Polyjuice
Usage:
    polyjuice.py (-h | --help)
    polyjuice.py [-lm]  <input_path> <output_path> <config_file> [-s=<subid>]
    polyjuice.py [-lcm] (<config_file>) [-s=<subid>]

Options:
  -h --help                     Show this message and exit
  -l --log                      Give progress of program
  -c --config                   Use config file to get input and output paths
  -m --meta                     Get the MetaData
  -s <subid> --subid=<subid>                    Set an explicit subject id for all the files. This works like the id csv

Instructions:
    Run polyjuice on individual files, ISOs, or directories. This will give an ouput folder
containing dicom files that have had their tags cleaned according to your standards set in the config file.
$ ./polyjuice.py path/to/input path/to/output
If you put your inputs and outputs in the config file, you can use the flag -c and write:
$ ./polyjuice.py
In order to ZIP your Cleaned Output Directory, add the -z flag.
"""

import os
import os.path
import shutil
import yaml
import time
import csv
from docopt import docopt
from lumberjack import Lumberjack
from filch import DicomCaretaker
from dicom_image import DicomImage

CONFIG_PATH = '<config_file>'
INPUT_DIR = '<input_path>'
OUTPUT_DIR = '<output_path>'
_print_log = '--log'
_use_config = '--config'
metadata_flag = '--meta'
dicom_folders = []
unknown_ids = []

def go_to_library(config_path):
    #Read in the config file. If the config file is missing or the wrong format, exit the program.
    try:
        with open(config_path, 'r') as config_file:
            config = yaml.load(config_file.read())
    except Exception as e:
        print("Error: Check config file")
        exit()
    return config

def ask_hermione(out_dir):
    #Check if directory exists. If not, create it.
    if not os.path.exists(out_dir):
        try:
            os.makedirs(out_dir)
        except Exception as e:
            raise e

def browse_restricted_section(parent_file, out_dir, zip_dir, modifications, id_pairs, log, get_metadata):
    #Walk through directories and send individual files to be cleaned.

    editor = DicomCaretaker()

    if os.path.isfile(parent_file):
        try:
            if parent_file.endswith(".iso"):
                # Mount and unmount ISO
                new_parent_dir = editor.mount_iso(parent_file, out_dir)
                browse_restricted_section(new_parent_dir, out_dir, zip_dir, modifications, id_pairs, log, get_metadata)
                editor.unmount_iso()
            else:
                #Send file to be cleaned
                brew_potion(editor, parent_file, out_dir, modifications, id_pairs, log, get_metadata)
        except Exception as e:
            print("{} failed".format(name))
            print (str(e))
            failure_message = "{} failed".format(name) + "\n" + str(e)
            log(failure_message)

    else:
        for path, subdirs, files in os.walk(parent_file):
            for name in files:
                path_message = os.path.join(path, name)
                log(path_message)
                try:
                    check_file_type = os.path.join(path, name)
                    working_file = os.path.join(path, name)
                    if check_file_type.endswith(".iso"):
                        # Mount and Unmount ISO
                        new_parent_dir = editor.mount_iso(working_file, out_dir)
                        browse_restricted_section(new_parent_dir, out_dir, zip_dir, modifications, id_pairs, log, get_metadata)
                        editor.unmount_iso()
                    else:
                        # Send file to be cleaned
                        brew_potion(editor, working_file, out_dir, modifications, id_pairs, log, get_metadata)

                except Exception as e:
                    print("{} failed".format(name))
                    print (str(e))
                    failure_message = "{} failed".format(name) + "\n" + str(e)
                    log(failure_message)
    return

def brew_potion(editor, working_file, out_dir, modifications, id_pairs, log, get_metadata=False):
    """
    Use DicomCaretaker to clean files and find approprite folders to save the output

    If get_metadata is passed a file with the tags of the image will be written to the same
    location as the image with the same name except for a .json extension
    """
    try:

        name = os.path.basename(working_file)
        with open(working_file) as working_file:
            working_message = "Working on {}".format(name)
            log(working_message)

            image = DicomImage(working_file)


            id_issue = editor.scrub(image, modifications, id_pairs, log, unknown_ids)

            if id_issue:
                return

            folder_name = editor.get_folder_name(image)
            identified_folder = os.path.join(out_dir, folder_name)

            if not os.path.exists(identified_folder):
                ask_hermione(identified_folder)
                dicom_folders.append(identified_folder)

            editor.save_output(image, identified_folder, name, get_metadata)
            saving_message = "Saved to {}".format(identified_folder)
            log(saving_message)

    except Exception as e:
        print("{} failed".format(name))
        failure_message = "{} failed".format(name) + "\n" + str(e)
        log(failure_message)
    return

def zip_files(dicom_folders, zip_dir, log):
    #Zip folders with cleaned DICOM images and move them to zip directory specified in config file
    for folder in dicom_folders:
        shutil.make_archive(folder, 'zip', folder)
        zipped_message = "{} archived".format(folder)
        log(zipped_message)

        ask_hermione(zip_dir)
        os.system("mv {}.zip {}".format(folder, zip_dir))
        move_zip_message = "{} moved to {}".format(folder, zip_dir)
        log(move_zip_message)

def find_config():
    my_config_path = ""
    current_path = os.getcwd()
    for path, subdirs, files in os.walk(current_path):
        for name in files:
            if name == 'config.yaml':
                return os.path.join(path, name)
    exit('No config found')

def get_id_mapping(config, args):
    """
    We want to support 1 to 1 mapping as well as specifiying a single
    subject id for all files
    """
    if not args.get('--subid'):
        reset_IDS = config.get('new_IDs')
        try:
            with open(reset_IDS, mode='r') as in_oldIDfile:
                rows = csv.reader(in_oldIDfile)
                id_pairs = {cols[0]:cols[1] for cols in rows}
        except Exception as e:
            print("Check CSV. \n" + str(e))
            return
        return id_pairs
    else:
        return {
            '__ALL__': args.get('--subid')
        }

def main(args):
    if not args[CONFIG_PATH]:
        args[CONFIG_PATH] = find_config()

    print(args)
    config = go_to_library(args[CONFIG_PATH])
    modifications = config.get('modifications')
    get_metadata = args.get(metadata_flag)

    id_pairs = get_id_mapping(config, args)

    zip_dir = config.get('zip')
    print("zip folder " + str(zip_dir))

    verbose = args[_print_log]

    if args[_use_config]:
        # path roots for clean files
        in_root = config.get('in_data_root')
        out_root = config.get('out_data_root')
        # dicts with 'input' and 'output' props that tell what to clean and where to put it
        io_pairs = config.get('io_pairs')

        for io_pair in io_pairs:
            out_dir = os.path.join(out_root, io_pair['output'])
            ask_hermione(out_dir)
            log_path = os.path.join(out_dir, 'log.txt')
            log = Lumberjack(log_path, verbose)
            parent_file = os.path.join(in_root, io_pair['input'])

            browse_restricted_section(parent_file, out_dir, zip_dir, modifications, id_pairs, log, get_metadata)

    else:
        #Loop through ISOs and subdirectories
        parent_file = args[INPUT_DIR]
        out_dir = args[OUTPUT_DIR]
        ask_hermione(out_dir)
        log_path = os.path.join(out_dir, 'log.txt')
        log = Lumberjack(log_path, verbose)


        browse_restricted_section(parent_file, out_dir, zip_dir, modifications, id_pairs, log, get_metadata)

    zip_files(dicom_folders, zip_dir, log)

def poly_run():
    args = docopt(docstr)
    main(args)

if __name__ == '__main__':
    poly_run()
    exit()
