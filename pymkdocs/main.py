#!/usr/bin/env python
import os
import sys
from subprocess import call, Popen
import webbrowser
import traceback
from pymkdocs import __version__, write_doc, RAW_MODE, MAGIC_MODE

def main(argv=None):
    args = __parse_args(sys.argv if argv is None else argv)
    if isinstance(args,int): return args
    src, dest, is_serve, options = args
    try: 
        write_doc(src, dest, options)
        os.chdir(dest)
        call(["mkdocs", "build", "--clean"])    
        if is_serve:
            Popen(["mkdocs", "serve"])
            webbrowser.open("http://127.0.0.1:8000/")    
        return 0                
    except Exception as error:
        print("[-] Error ", str(error))
        traceback.print_exc()
        return 1

def __parse_args(argv):
    # Note argparse wasn't employed simply to avoid that dependency...
    HELP_SWITCHES      = ["-h","--help","/?"]
    MAGIC_SWITCH       = "-m"
    RAW_SWITCH         = "-r"     
    SOURCE_SWITCH      = "-c"
    SERVE_SWITCH       = "-s"
    TITLE   = "| pyMkDocs |"
    VERSION = "v.{0}".format( __version__ )
    DESCR   = "This utility generates MkDocs websites from Python source code."
    USAGE   =("Help:  pymkdocs -h/--help\n" 
            "Usage: pymkdocs source[,source2,...] destination [{0}/{1}] [{2}] [{3}]\n"
            "{0}: magic mode (default) / {1}: raw mode\n"
            "{2}: include source code\n"
            "{3}: serve test site\n"
            "source: module name or path; comma-separate multiple sources\n").format( 
            MAGIC_SWITCH, RAW_SWITCH, SOURCE_SWITCH, SERVE_SWITCH)
 
    argv = sys.argv if argv is None else argv
    arg_count = len(argv)-1
    switches = argv[2:]
         
    is_invalid = arg_count < 2    
    is_help = False
    for switch in HELP_SWITCHES:
        is_help=switch in argv
        if is_help: break        
    if is_invalid or is_help:
        print(TITLE)
        print(VERSION)
        print(DESCR)
        print(USAGE)
        return 1 if is_invalid else 0
    
    src      = argv[1] 
    dest     = argv[2]   
    is_serve = SERVE_SWITCH in switches
    mode     = RAW_MODE if RAW_SWITCH in switches else MAGIC_MODE  
    options  = {
          "mode": mode
        , "is_source_shown": SOURCE_SWITCH in switches
        , "ignore_prefix": '_' if mode==MAGIC_MODE else None         
        }
    return src, dest, is_serve, options 
     
if __name__ == "__main__": sys.exit(main(sys.argv))
