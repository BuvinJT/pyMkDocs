# ----------------
import ast
import inspect
import importlib
import os
import sys
import platform
import glob
import traceback
import operator 
import tempfile
import subprocess
import shutil
from future.utils import string_types
import collections
# ----------------
 
RAW_MODE, MAGIC_MODE = range(2)
"""
Parsing Mode. See the ReadMe for info.
"""

SPACE           = ' '
SPACE_HTML      = '&nbsp;'
TAB             = '\t'
TAB_HTML        = 4 * SPACE_HTML
TAB_SPACES      = 4 * SPACE
NEW_LINE        = '\n'
DOT             = '.'
DOT_PY_EXT      = '.py'
PY_COMMENT_CHAR = '#'
TRIPLE_DOUBLE   = '"""'

MAGIC_START_DOC_COMMENT     = '# docs >'
MAGIC_APPEND_DOC_COMMENT    = '# docs >>'

MAGIC_PROSE_COMMENT_START   = '""" docs : prose'
MAGIC_PROSE_COMMENT_END     = TRIPLE_DOUBLE

MAGIC_VIRTUAL_COMMENT_START = '""" docs : virtual_code'
MAGIC_VIRTUAL_COMMENT_END   = TRIPLE_DOUBLE

MAGIC_VIRTUAL_VALUE_COMMENT     = 'docs : virtual_value=' 
MAGIC_CONDITIONAL_VALUE_COMMENT = 'docs : conditional_value' 

MAGIC_MODDOC_COMMENT        = '# docs : __doc__' 

MAGIC_NULL                  = 'null'
MAGIC_TAB                   = '<tab>'
MAGIC_SPACE                 = '<sp>'

TXT,SRC=range(2)

class_name_md = (
    "## **{0}**`#!py3 class` {{ #{1} data-toc-label={0} }}\n\n".format
)  # name, toc_name
base_classes_hdr_md = (
    "\n**Base Classes:**\n\n".format    
)    
base_class_md = (
    "{0}".format
)  # base name
base_class_sep = ', '
magic_methods_hdr_md = (
    "\n**Magic Methods:**\n\n".format    
)    
summary_level_link_md = " - [`{1}`](#{0}.{2})\n".format # class, name, toc_name
init_hdr_md = (
    " - [`__init__`](#{0}-init)\n".format
)  # name
static_method_name_md = (
    "### *{0}*.**{1}**`#!py3 {3}` {{ #{0}.{2} data-toc-label={1} }}\n\n".format
)  # class, name, toc_name, args
object_method_name_md = (
    "### *obj*.**{1}**`#!py3 {3}` {{ #{0}.{2} data-toc-label={1} }}\n\n".format
)  # class, name, toc_name, args
static_attribute_name_md = ( 
    "### *{0}*.**{1}** *{3}* default: *{4}* {{ #{0}.{2} data-toc-label={1} }}\n\n".format
)  # class, name, toc_name, type, value
object_attribute_name_md = ( 
    "### *obj*.**{1}** *{3}* default: *{4}* {{ #{0}.{2} data-toc-label={1} }}\n\n".format
)  # class, name, toc_name, type, value

init_md = (
    "### **{0}**`#!py3 {2}` {{ #{0}-init data-toc-label=\"&lowbar;&lowbar;init&lowbar;&lowbar;\" }}\n\n".format
)  # name, toc_name, args
var_md = ( 
    "### **{0}** *{2}* default: *{3}* {{ #{1} data-toc-label={0} }}\n\n".format
)  # name, toc_name, type, default
var_cond_val_md = ( 
    "### **{0}** *{2}* default: <span style=""color:gray"">&lt;{3}&gt;</span> {{ #{1} data-toc-label={0} }}\n\n".format
)  # name, toc_name, type, default
all_vars_md= (
    "## **Constants and Globals** {{ #Constants-and-Globals data-toc-label=\"Constants and Globals\" }}\n\n".format
)  
all_funcs_md = (
    "## **Functions** {{ #Functions data-toc-label=Functions }}\n\n".format
)  # name
function_name_md = (
    "### **{0}**`#!py3 {2}` {{ #{1} data-toc-label={0} }}\n\n".format
)  # name, toc_name, args
doc_md = "{}\n".format  # doc
source_md = (
    '\n\n??? info "Source Code" \n\t```py3 linenums="1 1 2" \n{}\n\t```\n'.
    format
)  # source

_old_docs=[]
_new_docs=[]

def __build_labeled_toc_section( label: str, toc_entries: str ) -> str:
    """
    Wrap toc_entries under a labeled sub-section for multi-source nav.
    For a single-page source uses inline format: ``- label: page.md``.
    For multi-page sources nests items one indent level deeper.
    """
    ref_tab    = 2 * TAB_SPACES  # 8 spaces — standard toc item indent
    extra_tab  = TAB_SPACES      # 4 extra spaces for nested items
    entry_lines = [l for l in toc_entries.splitlines(keepends=True) if l.strip()]
    if not entry_lines:
        return ""
    # Single entry with no inline key → use "- label: page.md" shorthand
    if len(entry_lines) == 1:
        entry = entry_lines[0].strip()
        if entry.startswith("- ") and ": " not in entry:
            page = entry[2:].strip()
            return ref_tab + "- " + label + ": " + page + "\n"
    # Multiple entries (or already has key): nest under label
    result = ref_tab + "- " + label + ":\n"
    for line in entry_lines:
        result += extra_tab + line
    return result

def write_doc(src: str, dest: str, options: dict = None, _skip_yaml: bool = False):
    """
    Generate documentation from Python source. 
    
    **Parameters**    
    > **src:** `str` -- Source python import name OR directory path.
    >   May be a comma-delimited list of sources; each will appear as a
    >   labeled item in the Reference nav section.
    > **dest:** `str` -- Destination directory path.    
    > **options:** `dict` -- Extended options.
    
    **Returns**
    > `None`
    """        
    global _old_docs
    global _new_docs

    # Multi-source: comma-delimited list of sources
    sources = [s.strip() for s in src.split(',') if s.strip()]
    if len(sources) > 1:
        project_name = os.path.basename(os.path.abspath(dest))
        yaml_path    = os.path.join(dest, 'mkdocs.yml')
        doc_path     = os.path.join(os.path.abspath(dest), __docs_dir(yaml_path))
        if not os.path.isdir(doc_path): os.makedirs(doc_path)
        for cur_path, _, files in os.walk(doc_path):
            rel_dir_path = os.path.relpath(cur_path, doc_path)
            for file in files:
                if os.path.splitext(file)[1] == '.md':
                    _old_docs.append(os.path.normpath(
                        os.path.join(rel_dir_path, file)))
        combined_toc = ""
        for s in sources:
            sub_toc = write_doc(s, dest, options, _skip_yaml=True)
            if sub_toc:
                label = os.path.basename(os.path.normpath(s))
                combined_toc += __build_labeled_toc_section(label, sub_toc)
        if not combined_toc:
            raise ValueError("All the files seem invalid")
        write_mkdocs_yaml(yaml_path, project_name, combined_toc, doc_path)
        return

    #print( "write_doc", src, dest, options )
    project_name = os.path.basename(os.path.abspath(dest)) # resolves args e.g. simply "." for "this directory" 

    yaml_path = os.path.join(dest, 'mkdocs.yml')
    doc_path = os.path.join(os.path.abspath(dest), __docs_dir(yaml_path))
    if not os.path.isdir(doc_path): os.makedirs(doc_path)
    if not _skip_yaml:  # only scan for pre-existing docs on a top-level call
        for cur_path, _, files in os.walk(doc_path):
            rel_dir_path = os.path.relpath(cur_path, doc_path)
            for file in files:
                if os.path.splitext(file)[1]=='.md':
                    _old_docs.append(os.path.normpath(os.path.join(rel_dir_path, file)))
            
    toc = ""
    lines = []
        
    mode=options.get("mode",MAGIC_MODE)
    if mode==MAGIC_MODE: 
        path_head,path_tail=os.path.split( src )
        if len(path_head) > 0:
            orginal_wrkdir = os.path.abspath(os.curdir)
            os.chdir(path_head)              
        else: orginal_wrkdir = None    
        package_name = path_tail
        magic_init_path = __get_module_path( 
            package_name, is_extern_mem_space=True ) 
        #print( "package init_path", magic_init_path )               
             
        # Build the "markdown map" first via "magic comments"           
        mdMap={} # { mdfile_path : [(TXT,text_lines),(SRC,source_lines),...] }            
        try: 
            with open( magic_init_path, 'r' ) as f: init_content=f.read()
        except Exception as e:
            __on_err_exc("cannot read from path: %s" % (magic_init_path,), e)
        lines = init_content.split(NEW_LINE)
        mdfile_name = None        
        is_virtual_mode=False
        if MAGIC_START_DOC_COMMENT in init_content:
            is_virtual_line=False            
            source_lines=[]
            text_lines=None            
            for line in lines:
                clean_line = line.strip()
                
                if clean_line.startswith( MAGIC_MODDOC_COMMENT ):
                    try:    mdMap[mdfile_name]
                    except: mdMap[mdfile_name]=[]
                    mdMap[mdfile_name].append((TXT,[MAGIC_MODDOC_COMMENT]))
                    continue
                
                if clean_line.startswith( MAGIC_VIRTUAL_COMMENT_START ):
                    is_virtual_mode=True
                    is_virtual_line=True
                    continue
                if is_virtual_line and clean_line.startswith( 
                    MAGIC_VIRTUAL_COMMENT_END ):
                    is_virtual_line=False
                    continue                

                if clean_line.startswith( MAGIC_PROSE_COMMENT_START ):
                    text_lines=[]
                    continue                                    
                if text_lines is not None and clean_line.startswith( 
                    MAGIC_PROSE_COMMENT_END ):                    
                    try:    mdMap[mdfile_name]
                    except: mdMap[mdfile_name]=[]
                    if len(source_lines) > 0:        
                        mdMap[mdfile_name].append((SRC,source_lines))
                        source_lines=[]                                                     
                    mdMap[mdfile_name].append((TXT,text_lines))                    
                    text_lines=None
                    continue                                    
                    
                if clean_line.startswith( MAGIC_START_DOC_COMMENT ):
                    try: 
                        input_name=line.split( MAGIC_START_DOC_COMMENT )[1].strip()
                    except Exception as e: 
                        input_name=None
                        __on_warn_exc("processing magic comment: %s" % 
                                      (line,), e)
                    if input_name != mdfile_name:                                                                                 
                        if mdfile_name:
                            try:    mdMap[mdfile_name]
                            except: mdMap[mdfile_name]=[]
                            if text_lines is not None:
                                mdMap[mdfile_name].append((TXT,text_lines))
                                text_lines = None
                            if len(source_lines) > 0:        
                                mdMap[mdfile_name].append((SRC,source_lines))
                        mdfile_name=input_name
                        source_lines=[]             
                    continue 
                           
                if text_lines is not None: text_lines.append(line)    
                else: source_lines.append(line)          
                         
            if mdfile_name:
                try:    mdMap[mdfile_name]
                except: mdMap[mdfile_name]=[]
                if text_lines is not None:
                    mdMap[mdfile_name].append((TXT,text_lines))
                    text_lines = None
                if len(source_lines) > 0:
                    mdMap[mdfile_name].append((SRC,source_lines))
        else:                
            mdfile_name = "%s.md" % (package_name,) 
            mdMap[mdfile_name]=[(TXT,[MAGIC_MODDOC_COMMENT]),(SRC,lines)]  
                  
        package_path = os.path.dirname( magic_init_path )                  
        
        # Process "magic virtual code comments"
        # if there is virtual code, use a temp copy of the package, with that code 
        # enabled, and import it by path directly
        # otherwise, use the abstracted method to find the import naturally    
        if is_virtual_mode:
            #print( "virtual magic init!" )                
            tmp_dir_path = tempfile.mkdtemp()
            tmp_pkg_path = os.path.join(tmp_dir_path,package_name)
            shutil.copytree(package_path,tmp_pkg_path)
            tmp_file_path = os.path.join(tmp_pkg_path,'__init__.py')                    
            virtual_source = NEW_LINE.join(_to_virtual_lines(lines))
            with open( tmp_file_path, 'w' ) as f: f.write( virtual_source )
            if not orginal_wrkdir: orginal_wrkdir = os.path.abspath(os.curdir)
            os.chdir(tmp_dir_path)   
            magic_init_path = tmp_file_path

        # get a module object and all its identifiers, categorized, but not filtered
        module =(__get_import_by_path(magic_init_path) if is_virtual_mode else          
                 __get_import_module(package_name))        
        all_names = __get_all_names( module )    
        #print("module", module.__file__)
        #print("all_names", all_names)
        magic_moddoc = __markdown_safe( inspect.getdoc(module) or "" )
            
        # Process the "markdown map", generating the requested docs
        #print( "mdMap", mdMap )
        
        for mdfile_name in mdMap: 
            
            if mdfile_name==MAGIC_NULL: continue

            page_content = mdMap[mdfile_name]
            if page_content is None: continue
            
            mdfile_path = os.path.join(doc_path, mdfile_name)    
            md_file = open( mdfile_path, "w")
            _new_docs.append(mdfile_name)
            package_name = os.path.splitext(os.path.basename(mdfile_path))[0]
               
            #print("Writing document: %s" % (mdfile_name,))  
         
            for page_section in page_content:
                #print(page_section)
                sec_type, sec_lines = page_section
                if sec_type==TXT:
                    if sec_lines[0]==MAGIC_MODDOC_COMMENT:
                        md_file.write(magic_moddoc + NEW_LINE)
                        continue
                    md_file.write(NEW_LINE.join(sec_lines))
                    md_file.write(NEW_LINE)        
                if sec_type==SRC:             
                    parsed = __parse_sec_for_import_names( 
                        module, all_names, package_path, sec_lines )
                    #print( "parsed", parsed )
                    if not parsed: continue   
                    mod_info, class_info, func_info, var_info = parsed
                    #print( mod_info, class_info, func_info, var_info )                        
                    for name in mod_info:                        
                        __write_mod(md_file, mod_info[name], package_name, name, options)                             
                    for name in class_info: 
                        __write_class(md_file, class_info[name], name, options)
                    if len(func_info) > 0 and len(class_info) > 0: 
                        write_functions_header(md_file)
                    for name in func_info: 
                        __write_func(md_file, func_info[name], name, options)     
                    if len(var_info) > 0 and (len(func_info) > 0 or len(class_info) > 0): 
                        write_vars_header(md_file)
                    for name in var_info:  
                        __write_var(md_file, var_info[name], name, options)                           
            md_file.close()    
            try: toc += get_toc_lines_from_file_path(mdfile_name)
            except Exception as e: __on_warn_exc("TOC error",e) 

        # restore working directory and clean up temp files
        if orginal_wrkdir: os.chdir(orginal_wrkdir)
        if is_virtual_mode: shutil.rmtree(tmp_dir_path)                
    else:         
        code_path = os.path.abspath(src)
        package_name = code_path.split("/")[-1]
        root_path = os.path.dirname(code_path)
         
        # load the architecture of the module
        ign_pref_file = "__"
        full_list_glob = glob.glob(code_path + "/**", recursive=True)
        list_glob = [
            p
            for p in full_list_glob
            if "/" + ign_pref_file not in p and os.path.isfile(p) and p[-3:] == ".py" \
                and "__init__" not in p
        ]

        # write every markdown files based on the architecture
        #Since windows and Linux platforms utilizes different slash in their file structure
        system_slash_style = {"Windows": "\\", "Linux": "/"}                
        for mod in list_glob:
            module_name = mod[len(root_path) + 1 : -3]\
                .replace(system_slash_style.get(platform.system(), "/"), ".")
            mdfile_path = os.path.join(
                doc_path, mod[len(code_path) + 1:-3] + ".md"
            )
            mdfile_name = mdfile_path[len(doc_path) + 1:]            
            try:
                write_module(root_path, module_name, mdfile_path, options)
                toc += get_toc_lines_from_file_path(mdfile_name)
            except Exception as e: __on_warn_exc("TOC error", e)

    #print( "toc", toc )
    if not _skip_yaml and len(toc) == 0:
        raise ValueError("All the files seem invalid")
    
    if _skip_yaml:
        return toc

    write_mkdocs_yaml(yaml_path, project_name, toc, doc_path)

def write_module(
    path_to_home: str,
    module_import: str,
    path_to_md: str,
    options: dict = None
):
    """
    Generate a Markdown file based on the content of a Python module

    **Parameters**
    > **path_to_home:** `str` -- path to the root of the project (2 steps before the `__init__.py`)
    > **module_import:** `str` -- module name (ex: `my_package.my_module`)
    > **path_to_md:** `str` -- path to the output markdown file
    > **options:** `dict` -- extended options

    """
    global _new_docs

    package_path = os.path.abspath(path_to_home)
    package_name = module_import.split(".")[0]
    sys.path.insert(0, package_path)

    try:
        module = importlib.import_module(
            module_import, package=package_name
        )
    except ModuleNotFoundError as error:
        raise ModuleNotFoundError(str(error) + " in " + module_import)

    clas  = [create_class(module, package_name, n, o, options)
            for n, o in inspect.getmembers(module, inspect.isclass)]
    funs  = [create_fun(n, o, options)
            for n, o in inspect.getmembers(module, inspect.isfunction)]
    gvars = [create_var(n, o, o, __var_docstring(module,n), options)  
            for n, o in __get_import_vars(module)]

    if not os.path.isdir(os.path.dirname(path_to_md)):
        os.makedirs(os.path.dirname(path_to_md))        
    md_file = open(path_to_md, "w")
    _new_docs.append(os.path.basename(path_to_md))
    for c in clas:
        write_class(md_file, c, options)
        md_file.writelines("""\n______\n\n""")
    for f in funs:
        write_function(md_file, f, options)
        md_file.writelines("""\n______\n\n""")
    for v in gvars:
        write_variable(md_file, v, options)
        md_file.writelines("""\n______\n\n""")
    md_file.close()

def write_class(md_file, clas, options):
    """
    Add the documentation of a class to a markdown file

    **Parameters**
    > **md_file:** `file` -- file object of the markdown file
    > **clas:** `dict` -- class information organized as a dict (see `create_clas`)
    > **options:** `dict` -- extended options
    
    """
    md_file.writelines(class_name_md(
        __html_escape_magic_name( clas["name"] ),
        __toc_escape_magic_name(  clas["name"] ) ))
    md_file.writelines(doc_md(clas["doc"]))

    if len(clas["base"]) > 0:
        md_file.writelines( base_classes_hdr_md() )
        base_class_list=""
        for i, c in enumerate(clas["base"]):
            if i > 0: base_class_list += base_class_sep
            base_class_list += base_class_md(c)
        md_file.writelines(base_class_list + '\n\n')

    if clas["is_init"]:        
        md_file.writelines( magic_methods_hdr_md() )
        md_file.writelines(init_hdr_md(__toc_escape_magic_name(clas["name"])))        

    if len(clas["instance_methods"]) > 0 or clas["is_init"]:
        md_file.writelines("\n**Instance Methods:** \n\n")
        for m in clas["instance_methods"]:
            md_file.writelines( summary_level_link_md(
                __toc_escape_magic_name(clas["name"]),
                m["name"], __toc_escape_magic_name(m["name"]) ))
            
    if len(clas["instance_attributes"]) > 0:
        md_file.writelines("\n**Instance Attributes:** \n\n")
        for m in clas["instance_attributes"]:
            md_file.writelines( summary_level_link_md(
                __toc_escape_magic_name(clas["name"]),
                m["name"], __toc_escape_magic_name(m["name"]) ))

    if len(clas["class_methods"]) > 0:
        md_file.writelines("\n**Class/Static Methods:** \n\n")
        for f in clas["class_methods"]:
            md_file.writelines( summary_level_link_md(
                __toc_escape_magic_name(clas["name"]),
                m["name"], __toc_escape_magic_name(m["name"]) ))

    if len(clas["class_attributes"]) > 0:
        md_file.writelines("\n**Class/Static Attributes:** \n\n")
        for m in clas["class_attributes"]:
            md_file.writelines( summary_level_link_md(
                __toc_escape_magic_name(clas["name"]),
                m["name"], __toc_escape_magic_name(m["name"]) ))

    md_file.writelines(NEW_LINE)

    if clas["is_init"]:         
        md_file.writelines(init_md(
            __html_escape_magic_name( clas["name"] ),
            __toc_escape_magic_name(  clas["name"] ),
            clas["args"]))            
        md_file.writelines(doc_md(clas["init_doc"]))
        if options.get("is_source_shown",False): 
            md_file.writelines(source_md(clas["init_source"]))

    for m in clas["instance_methods"]:
        write_method(md_file, m, clas, False, options)    
    for m in clas["instance_attributes"]:
        write_attribute(md_file, m, False, options, clas)    

    for f in clas["class_methods"]:
        write_method( md_file, f, clas, True, options)  
    for m in clas["class_attributes"]:
        write_attribute(md_file, m, True, options, clas)    

    for m in clas["class_attributes"]:
        if m["class"]: write_class(md_file, m["class"], options)

def write_function(md_file, fun, options):
    """
    Add the documentation of a function to a markdown file

    **Parameters**
    > **md_file:** `file` -- file object of the markdown file
    > **fun:** `dict` -- function information organized as a dict (see `create_fun`)
    > **options:** `dict` -- extended options
 
    """
    if fun is None: return
    md_file.writelines(function_name_md(
        __html_escape_magic_name( fun["name"] ), 
        __toc_escape_magic_name(  fun["name"] ),
        fun["args"]))
    md_file.writelines(doc_md(fun["doc"]))    
    if options.get("is_source_shown",False): 
        md_file.writelines(source_md(fun["source"]))

def write_method(md_file, method, clas, is_static, options):
    """
    Add the documentation of a method to a markdown file

    **Parameters**
    > **md_file:** `file` -- file object of the markdown file
    > **method:** `dict` -- method information organized as a dict (see `create_fun`)
    > **class:** `dict` -- class information organized as a dict (see `create_fun`)
    > **options:** `dict` -- extended options
    
    """
    if method is None: return
    md_file.writelines(
        static_method_name_md( 
            __html_escape_magic_name(   clas["name"] ), 
            __html_escape_magic_name( method["name"] ),
            __toc_escape_magic_name(  method["name"] ),
            method["args"] )
        if is_static else
        object_method_name_md( 
            __html_escape_magic_name(   clas["name"] ),            
            __html_escape_magic_name( method["name"] ), 
            __toc_escape_magic_name(  method["name"] ),
            method["args"] )
    )
    md_file.writelines(doc_md(method["doc"]))
    if options.get("is_source_shown",False):
        md_file.writelines(source_md(method["source"]))

def write_variable(md_file, var, options):
    """
    Add the documentation of a function to a markdown file

    **Parameters**
    > **md_file:** `file` -- file object of the markdown file
    > **att:** `dict` -- attribute information organized as a dict (see `create_att`)
    > **options:** `dict` -- extended options

    """
    if var is None: return
        
    doc_lines_in  = var["doc"].split(NEW_LINE)
    doc_lines_out = []
    magic_value = None
    is_magic_cond_val = False
    for line in doc_lines_in:
        line = line.strip()
        if   line.startswith( MAGIC_VIRTUAL_VALUE_COMMENT ): 
            try: magic_value = line.split( MAGIC_VIRTUAL_VALUE_COMMENT )[1].strip()
            except: pass         
        elif line.startswith( MAGIC_CONDITIONAL_VALUE_COMMENT ): is_magic_cond_val = True
        else : doc_lines_out.append( line )
    doc = NEW_LINE.join(doc_lines_out)            
    value = magic_value if magic_value else var["value"]
    
    md_file.writelines(   
        var_cond_val_md(
            __html_escape_magic_name(var["name"]),
            __toc_escape_magic_name( var["name"]),
            var["type"], value )
        if is_magic_cond_val else  
        var_md(
            __html_escape_magic_name(var["name"]),
            __toc_escape_magic_name( var["name"]),
            var["type"], value ) 
    )
    md_file.writelines(doc_md(doc))

def write_attribute(md_file, att, is_static, options, clas=None):
    """
    Add the documentation of a function to a markdown file

    **Parameters**
    > **md_file:** `file` -- file object of the markdown file
    > **att:** `dict` -- attribute information organized as a dict (see `create_att`)
    > **options:** `dict` -- extended options

    """
    if att is None: return
    md_file.writelines(
        static_attribute_name_md(
            __html_escape_magic_name( clas["name"] ),
            __html_escape_magic_name(  att["name"] ),
            __toc_escape_magic_name(   att["name"] ),
            att["type"], att["value"] )
        if is_static else
        object_attribute_name_md(
            __html_escape_magic_name( clas["name"] ),
            __html_escape_magic_name(  att["name"] ),
            __toc_escape_magic_name(   att["name"] ),
            att["type"], att["value"] )
    ) 
    md_file.writelines(doc_md(att["doc"]))

def write_functions_header(md_file): md_file.writelines(all_funcs_md())

def write_vars_header(md_file): md_file.writelines(all_vars_md())

def write_mkdocs_yaml(path_to_yaml: str, project_name: str, toc: str,
                      doc_path: str ):
    """
    Generate the YAML file that contains the website configs

    **Parameters**
    > **path_to_yaml:** `str` -- path to the output YAML file
    > **project_name:** `str` -- name of the project
    > **toc:** `str` -- the toc and the all hierarchy of the website
    """

    global _old_docs
    global _new_docs
    
    ref_sec_name = "Reference"
    ref_tab  = 2*TAB_SPACES

    if os.path.isfile(path_to_yaml):            
        is_index_doc     = True
        ref_sec_prefix   = "- " + ref_sec_name
        prior_yaml_start = ""
        prior_yaml_end   = ""    
        is_ref=False
        is_end=False
        with open(path_to_yaml, "r") as f:
            for ln in f:
                if is_end: prior_yaml_end += ln
                elif is_ref:
                    is_end = len(ln.strip()) > 0 and not ln.startswith(ref_tab)
                    if is_end: prior_yaml_end += ln                    
                else: 
                    is_ref = ln.strip().startswith(ref_sec_prefix)
                    prior_yaml_start += ln                    
        content = "{}{}{}".format(prior_yaml_start, toc, prior_yaml_end)                            
    else :
        toc_docs = [d for d in _old_docs if d not in _new_docs]
        is_index_doc = 'index.md' in toc_docs
        if is_index_doc: toc_docs.remove('index.md') 
        toc_docs.sort()
        toc_docs.insert(0,'index.md') 
        nav = ''         
        toc_fmt = '- {0}: {1}\n'
        home_entry = TAB_SPACES + toc_fmt.format('Home','index.md')
        ref_entry = TAB_SPACES + toc_fmt.format(ref_sec_name,'')
        for doc in toc_docs:
            if doc in _new_docs: continue
            if doc=='index.md': nav += home_entry
            else : nav += get_toc_lines_from_file_path(doc,is_top=True)
        nav += ref_entry.rstrip()
        content = """site_name: {}
theme:
  name: 'material'
nav:
{}
{}
markdown_extensions:
    - toc:
        toc_depth: 3
        permalink: True
    - extra
    - smarty
    - codehilite
    - admonition
    - pymdownx.details
    - pymdownx.superfences
    - pymdownx.emoji
    - pymdownx.inlinehilite
    - pymdownx.magiclink
""".format(project_name, nav, toc)
         
    yaml_file = open(path_to_yaml, "w")
    yaml_file.writelines(content)
    yaml_file.close()

    if not is_index_doc:
        index_path = os.path.join(doc_path, 'index.md')
        write_indexmd(index_path, project_name)

def write_indexmd(path_to_indexmd: str, project_name: str):   
    indexmd_file = open(path_to_indexmd, "w")
    content = """# {0} Documentation
Welcome to the {0} library documentation site!
""".format(project_name)
    indexmd_file.writelines(content)
    indexmd_file.close()

def get_toc_lines_from_file_path(mdfile_name,is_top=False):
    tab = TAB_SPACES if is_top else 2*TAB_SPACES
    mdfile_name = mdfile_name.replace('\\','/')
    lines = ""
    for i, layer in enumerate(mdfile_name.split("/")):
        if i + 1 != len(mdfile_name.split("/")):
            lines += tab * (i + 1) + "- " + layer + ":" + NEW_LINE
        else:
            lines += tab * (i + 1) + "- " + mdfile_name + NEW_LINE
    return lines

def create_class(module, package_name, name: str, obj, options: dict):
    """
    Generate a dictionary that contains the information about a class

    **Parameters**
    > **name:** `str` -- name of the class as returned by `inspect.getmembers`
    > **obj:** `object` -- object of the class as returned by `inspect.getmembers`
    > **options:** `dict` -- extended options

    **Returns**
    > `dict` -- with keys:
    >  - *name*, *obj* -- the class name and object as returned by `inspect.getmembers`
    >  - *module* -- name of the module
    >  - *path* -- path of the module file
    >  - *base* -- base class(es) (top down order)
    >  - *doc* -- docstring of the class
    >  - *source* -- source code of the class
    >  - *is_init* -- class definition includes __init__
    >  - *args* -- arguments of the class as a `inspect.signature` object
    >  - *init_doc* -- docstring of the __init_ method
    >  - *init_source* -- source code of the __init_ method
    >  - *functions* -- list of functions that are in the class (formatted as dict)
    >  - *methods* -- list of methods that are in the class (formatted as dict)
    >  - *attributes* -- list of attributes that are in the class (formatted as dict)
    """
    clas = {}
            
    clas["name"]   = name
    clas["obj"]    = obj
    
    try:    clas["module"] = inspect.getmodule(obj).__name__
    except: clas["module"] = ""
    try:    clas["path"]   = inspect.getmodule(obj).__file__
    except: clas["path"]   = None   
    try:    clas["doc"]    = __markdown_safe( inspect.getdoc(obj) or "" )
    except: clas["doc"]    = ""    
    try:    clas["source"] = __prep_source(inspect.getsource(obj))
    except: clas["source"] = ""
    try:    clas["args"]   = inspect.signature(obj)
    except: clas["args"]   = ""
    
    clas["is_init"]             = False
    clas["init_doc"]            = ""
    clas["init_source"]         = ""        
    clas["class_attributes"]    = []
    clas["class_methods"]       = []
    clas["instance_methods"]    = []    
    clas["instance_attributes"] = []        
           
    methods = []
    all_method_names = []
    for n, o in inspect.getmembers(obj, inspect.isfunction):
        try: 
            # sometimes inspect reports an object to be function when it should
            # be a method! This corrects for that mistake.            
            is_method = len(
                [p for i,p in enumerate(inspect.signature(o).parameters)
                 if i==0 and p=='self'] ) > 0
            if is_method: 
                methods.append( (n,o) )
                continue
        except: pass                         
        all_method_names.append(n)
        f = create_fun(n, o, options)        
        if f: clas["class_methods"].append(f)
                        
    # combine the methods already found in the functions list with those 
    # returned by inspect   
    methods.extend( inspect.getmembers(obj, inspect.ismethod) )
    methods.sort(key=operator.itemgetter(0))
    default_inst = None
    default_parms = []
    for n, o in methods:
        all_method_names.append(n)
        if n=='__init__':
            clas["init_doc"] = inspect.getdoc(o)
            clas["init_source"] = __prep_source(inspect.getsource(o))
            (args, 
             varargs, varkw, defaults, kwonlyargs, kwonlydefaults, # @UnusedVariable  
             annotations) = inspect.getfullargspec(o)
            #print( name, args, varargs, varkw, defaults, 
            #       kwonlyargs, kwonlydefaults, annotations )    
            for arg in args:
                if arg=='self': continue
                annot = annotations.get(arg)                
                default_parms.append( '%s()' % (annot.__name__,)
                                     if annot and hasattr(annot, '__name__') else 'None' )             
        else :
            f = create_fun(n, o, options)
            if f: clas["instance_methods"].append(f)

    import_name = name.split('.')[0]
    import_statement = "from %s import %s" % (package_name, import_name)               
    create_statement = "%s(%s)" % (name, ','.join(default_parms))            
    try: 
        #print( import_statement + "\n" + create_statement + "\n" )                
        exec( import_statement )               
        default_inst = eval( create_statement )
    except: pass
    #except Exception as e:
    #    __on_warn_exc( "Can't create default constructed object:\n" +
    #                   import_statement + "\n" +
    #                   create_statement + "\n", e )                
    
    # get class attributes         
    builtin_names = __builtin_object_member_names()
    v = None    
    for n, o in inspect.getmembers(obj):        
        if n not in builtin_names and n not in all_method_names:
            if default_inst:
                try: v = getattr(default_inst, n, None)
                except Exception: v = None
            d = None # updated later via ast parsing
            c =(create_class(module, package_name, "%s.%s" % (name,n), o, options) 
                if inspect.isclass(o) else None )
            a = create_att(n, o, v, d, c, options)
            if a: clas["class_attributes"].append(a)
     
    # use ast for additional inspection / parsing  
    class ClassVisitor(ast.NodeVisitor):
        def visit_ClassDef(self, node):            
            if node.name==name:
                # "back fill" class attribute docstrings
                self.__get_class_att_docstrings( node )
                # get instance attributes
                InitVisitor().visit(node)

        def __get_class_att_docstrings(self, node):
            for i, statement in enumerate(node.body):                
                if isinstance(statement, ast.Assign):
                    for target in statement.targets:                        
                        att_names=[]
                        if isinstance(target, ast.Name):
                            att_names.append( target.id )
                        elif isinstance(target, ast.Tuple):
                            for el in target.elts:
                                if isinstance(el, ast.Name):
                                    att_names.append( el.id )
                        if len(att_names) > 0:                                    
                            try:    next_statement=node.body[i+1]
                            except: next_statement=None
                            if( isinstance(next_statement, ast.Expr) and 
                                isinstance(next_statement.value, ast.Str) ):
                                doc = set_indent( next_statement.value.s, 0 )                                                            
                                for att_name in att_names:
                                    for j, att in enumerate(clas["class_attributes"]):
                                        if att["name"]==att_name:
                                            clas["class_attributes"][j]["doc"] = doc
                                            break
            
    class InitVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            if node.name != '__init__': return
            clas["is_init"] = True
            for i, statement in enumerate(node.body):                
                if isinstance(statement, ast.Assign):
                    for target in statement.targets:
                        if isinstance(target, ast.Attribute):
                            name = target.attr
                            #if isinstance(statement.value, ast.Name):
                            #    value = str(statement.value.id)
                            obj =( getattr(default_inst, name, None) 
                                   if default_inst else None )
                            try:    next_statement=node.body[i+1]
                            except: next_statement=None
                            if( isinstance(next_statement, ast.Expr) and 
                                isinstance(next_statement.value, ast.Str) ):
                                doc = set_indent( next_statement.value.s, 0 )                                
                            else: doc = None    
                            a = create_att(name, obj, obj, doc, None, options)
                            if a: clas["instance_attributes"].append(a)
    if clas["path"] :                                                             
        with open(clas["path"],'r') as f: 
            mod_source = make_virtual_code_real( f.read() )            
        ClassVisitor().generic_visit(ast.parse(mod_source))
    else: print("No path available for class", clas["name"] )     
    
    def __override_attributes( clas_attribs, derived_class_attribs ):
        for idx, inst_attrib in enumerate(clas_attribs):            
            for der_idx, der_attrib in reversed(list(enumerate(
                derived_class_attribs))):                 
                if der_attrib["name"] == inst_attrib["name"] : 
                    clas_attribs.pop( idx )    
                    clas_attribs.insert( idx, der_attrib )
                    derived_class_attribs.pop( der_idx )
        for der_attrib in derived_class_attribs:
            clas_attribs.append( der_attrib )
        return clas_attribs    
        
    root_name = name.split(".")[-1] 
    base_classes = [ c for c in reversed( inspect.getmro(obj) ) 
                     if c.__name__ not in [root_name,'object'] ]     
    clas["base"] = [ c.__name__ for c in base_classes ]
    if len(base_classes) > 0 :            
        clas_attribs_sv = clas["instance_attributes"].copy()
        clas["instance_attributes"] = []
        for class_name in clas["base"]:
            derived_class = __get_import_class( 
                module, package_name, class_name, options )
            if derived_class is None: continue
            clas["instance_attributes"] = __override_attributes( 
                clas["instance_attributes"], derived_class["instance_attributes"])
        clas["instance_attributes"] = __override_attributes( 
            clas["instance_attributes"], clas_attribs_sv)
                
    return clas

def create_fun(name: str, obj, options: dict):
    """
    Generate a dictionnary that contains the information about a function

    **Parameters**
    > **name:** `str` -- name of the function as returned by `inspect.getmembers`
    > **obj:** `object` -- object of the function as returned by `inspect.getmembers`
    > **options:** `dict` -- extended options

    **Returns**
    > `dict` -- with keys:
    >  - *name*, *obj* -- the function name and object as returned by `inspect.getmembers`
    >  - *module* -- name of the module
    >  - *path* -- path of the module file
    >  - *doc* -- docstring of the function
    >  - *source* -- source code of the function
    >  - *args* -- arguments of the function as a `inspect.signature` object
    """

    ignore_prefix = options.get("ignore_prefix")
    if ignore_prefix is not None and name[:len(ignore_prefix)]==ignore_prefix:
        return None

    fun = {}
    fun["name"] = name if name else 'undefined'
    fun["obj"] = obj
    fun["module"] = inspect.getmodule(obj).__name__
    fun["path"] = inspect.getmodule(obj).__file__
    fun["doc"] = __markdown_safe( inspect.getdoc(obj) or "" )
    fun["source"] = __prep_source(inspect.getsource(obj))
    fun["args"] = inspect.signature(obj)
    return fun

def create_var(name: str, obj, val, doc, options: dict):
    return create_att(name, obj, val, doc, None, options)

def create_att(name: str, obj, val, doc, clas, options: dict):
    """
    Generate a dictionary that contains the information about an attribute

    **Parameters**
    > **name:** `str` -- name of the attribute as returned by `inspect.getmembers`
    > **obj:** `object` -- object of the attribute as returned by `inspect.getmembers`
    > **options:** `dict` -- extended options

    **Returns**
    > `dict` -- with keys:
    >  - *name*, *obj* -- the attribute name and object as returned by `inspect.getmembers`
    >  - *doc* -- docstring of the attribute
    >  - *type* -- type of the attribute
    >  - *value* -- value of the attribute
    >  - *class* -- if attribute is, a dict with that class info
    """

    ignore_prefix = options.get("ignore_prefix")
    if ignore_prefix is not None and name[:len(ignore_prefix)]==ignore_prefix:
        return None

    if isinstance(val,string_types):
        val = ('"&lt;empty string&gt;"'  if len(val)==0 else 
               '"{0}"'.format(val) )    

    att = {}
    att["name"]  = '<undefined name>' if name is None else name  
    att["obj"]   = obj
    att["type"]  = __markdown_safe(type(obj)) 
    att["value"] = __markdown_safe(val)    
    att["doc"]   = __markdown_safe(doc or "")    
    att["class"] = clas    
    return att

def make_virtual_code_real( source:str ):
    """
    Convert all "virtual" code into "real" code.

    **Parameters**
    > **source:** `str` -- Source code of a function or a class

    **Returns**
    > `str` -- Source code with "virtual" code made real.
    """
    lines = source.split(NEW_LINE)
    is_virtual_line=False            
    source_lines=[]
    for line in lines:
        clean_line = line.strip()        
        if clean_line.startswith( MAGIC_VIRTUAL_COMMENT_START ):
            is_virtual_line=True
            continue
        if is_virtual_line and clean_line.startswith( 
            MAGIC_VIRTUAL_COMMENT_END ):
            is_virtual_line=False
            continue                
        source_lines.append(line)          
    return NEW_LINE.join(source_lines)                     
                                 
def rm_docstring_from_source( source:str ):
    """
    Remove the docstring from the source code of a function or a class

    **Parameters**
    > **source:** `str` -- Source code of a function or a class

    **Returns**
    > `str` -- Source code of a class without docstring
    """
    try:
        # remove the docstring, but retain other triple double comments 
        sections = source.split( TRIPLE_DOUBLE )
        head = sections[0]
        body = TRIPLE_DOUBLE.join( sections[2:] )
        
        # remove any trailing blank lines from head
        def __slice_end( lines ):
            for idx, ln in enumerate(reversed(lines)):
                if ln.strip() != '': return len(lines)-idx 
            return len(lines)
        lines = head.split( NEW_LINE )                        
        head = NEW_LINE.join( lines[:__slice_end( lines )] ) + NEW_LINE        
        
        # remove any leading blank lines from body
        def __slice_start( lines ):
            for idx, ln in enumerate(lines):
                if ln.strip() != '': return idx 
            return 0
        lines = body.split( NEW_LINE )        
        body = NEW_LINE.join( lines[__slice_start( lines ):] )
                
        # combine head and body, normalizing indent for resulting docs
        return set_indent( head + body, 1 )
    except: return source
    
def set_indent( s:str, lvl:int ):
    if not isinstance( s, string_types ): return s
    tabs = (lvl*TAB)
    def __first_line( lines ):
        for ln in lines:
            if ln.strip() != '': return ln 
        return lines[0]
    lines = s.split(NEW_LINE)
    #first_line = __first_line( lines )
    #lop_len = len(first_line) - len(first_line.lstrip())
    for i in range(len(lines)):
        try: lines[i] = tabs + lines[i].lstrip()
            #lines[i] = tabs + lines[i][lop_len:]
            #print("lines[i]",lines[i])
        except: pass
    return NEW_LINE.join(lines)

def __get_module_path( module_name: str, is_extern_mem_space=False ):
    """
    Attempt to import the module/package simply by name.
    If that import fails, check if this package is found on a path 
    relative to the working directory, otherwise raise an exception.
    """
    try:  
        if is_extern_mem_space:
            from sys import executable as py_path
            script=("import inspect; import {0}; print(inspect.getfile({0}));"
                    .format(module_name))
            #print(subprocess.list2cmdline([py_path,'-c',script]))
            path = subprocess.check_output([py_path,'-c',script]).strip().decode('utf-8')
            #print("path",path)
            if os.path.isfile(path): return path
            raise Exception() 
        else:
            exec( "import %s" % (module_name,) )
            return eval( "inspect.getfile( %s )" % (module_name,) )
    except Exception as e:
        path = os.path.join(os.path.abspath(module_name),'__init__.py')
        if os.path.isfile(path): return path
        # Fall back: search already-loaded modules for a name ending in this module
        suffix = "." + module_name
        for loaded_name, loaded_mod in list(sys.modules.items()):
            if (loaded_name == module_name or loaded_name.endswith(suffix)) and loaded_mod is not None:
                try:
                    fpath = inspect.getfile(loaded_mod)
                    if os.path.isfile(fpath): return fpath
                except: pass
        __on_err_exc("cannot resolve path for module %s" % 
                     (module_name,), e)    
     
def __get_import_module( module_name: str ):
    """
    Returns importlib module
    Attempt to import the module/package simply by name.
    If that import fails, try to import the package by relative path, 
    otherwise raise an exception.
    """
    try:    return __get_import_by_name( module_name, is_silent=True )
    except: return __get_import_by_path( __get_module_path( module_name ) )
   
def __get_import_by_name( name: str, is_silent=False, is_refresh=False ):            
    try: 
        if is_refresh:
            sys.modules.pop(name,None)
            importlib.invalidate_caches()         
        return importlib.import_module(name)
    except Exception as e:
        __on_err_exc("cannot acquire module: %s" % (name,), 
                     e, is_silent=is_silent)
                     
def __get_import_by_path( path: str, other_paths: list=None, 
                          is_silent=False, is_refresh=False  ):
    package_name = os.path.splitext(os.path.basename(path))[0]
    if package_name=='__init__':
        path = os.path.dirname(path)
        package_name = os.path.basename(path)
        path = os.path.dirname(path)
    else:
        file_dir = os.path.dirname(os.path.abspath(path))
        # Walk up to find the top-level package root (stop when no __init__.py)
        current_dir = file_dir
        parts = [package_name]
        while os.path.isfile(os.path.join(current_dir, '__init__.py')):
            parts.insert(0, os.path.basename(current_dir))
            parent = os.path.dirname(current_dir)
            if parent == current_dir:  # reached filesystem root
                break
            current_dir = parent
        if len(parts) > 1:
            # Module is inside a package; use full dotted name
            package_name = '.'.join(parts)
            path = current_dir
        else:
            # Standalone module; use its containing directory
            path = file_dir
    paths=[path]+(other_paths if other_paths else [])
    [sys.path.insert(0, p) for p in reversed(paths)]
    try:
        if is_refresh:
            sys.modules.pop(package_name,None)
            importlib.invalidate_caches()
        return importlib.import_module(package_name)
    except Exception as e:
        __on_err_exc("cannot acquire module: %s from %s" % 
                     (package_name,path), e)
    #finally: [sys.path.remove(p) for p in paths]
    
def __get_source_path( module, member_name ):
    for n, o in inspect.getmembers( module ):
        if n==member_name:             
            try: return inspect.getmodule(o).__file__
            except: return module.__file__                
                
def __get_all_names( module ):     
    mod_names   = [ n for n,_ in inspect.getmembers(module, inspect.ismodule) ]
    class_names = [ n for n,_ in inspect.getmembers(module, inspect.isclass) ] 
    func_names  = [ n for n,_ in inspect.getmembers(module, inspect.isfunction) ]
    var_names   = [ n for n,_ in __get_import_vars( module ) ]
    return mod_names, class_names, func_names, var_names

def __get_import_class_names( module ): 
    return [n for n,_ in inspect.getmembers(module, inspect.isclass)]

def __get_import_func_names( module ): 
    return [n for n,_ in inspect.getmembers(module, inspect.isfunction)]

def __get_import_class( module, package_name, classname: str, options: dict ): 
    for n, o in inspect.getmembers(module, inspect.isclass):
        if n==classname: return create_class(module,package_name, n, o, options)

def __get_import_func( module, funcname: str, options: dict ): 
    for n, o in inspect.getmembers(module, inspect.isfunction):
        if n==funcname: return create_fun(n, o, options)

def __get_import_var( module, varname: str, options: dict ):
    for n, o in __get_import_vars( module ):
        if n==varname:
            return create_var(n, o, o, __var_docstring(module,n), options)

def __docstring( ast_root_node, varname, mod_source ):
    """
    Returns docstring (as str), 
        or None if the variable is found but has no docstring
        or False if the variable is not found 
    Search only the top level of the root_node,
    because the definition of this type of docstring is:  
    "String literals occurring immediately after a simple assignment 
    at the top level of a module, class, or __init__ method...". 
    """    
    #print( "searching for var docstring", varname )
    doc_string = False    
    var_lineno = None    
    for child in ast.iter_child_nodes( ast_root_node ):        
        if var_lineno is None:            
            if   isinstance( child, ast.Assign ):    targets = child.targets
            elif isinstance( child, ast.AnnAssign ): targets = [child.target]
            elif isinstance( child, ast.Tuple  ):    targets = child.elts
            else:                                     targets = []            
            for target in targets:
                if isinstance( target, ast.Name ) and target.id==varname:
                    var_lineno = child.lineno
                    doc_string = None
                    break     
        else: # node immeaditely following assign
            if( isinstance( child, ast.Expr ) and 
                isinstance( child.value, ast.Str ) ):
                doc_string = child.value.s                                
            break                                             
         
    if doc_string != False:          
        if doc_string is None: 
            mod_lines  = mod_source.split( NEW_LINE )
            doc_string = __rawDocString( mod_lines, var_lineno )
        if doc_string is not None: doc_string = set_indent( doc_string, 0 )

    #print( "docstring: ", doc_string )             
    return doc_string

def __rawDocString( mod_lines, lineno ):    
    try:    next_line = mod_lines[ lineno ].strip()
    except: next_line = ""
    if next_line.startswith( TRIPLE_DOUBLE ):
        #print("triple double found on line %d"  % (node.lineno+1,) )
        line_parts = next_line.split( TRIPLE_DOUBLE )
        #print("line_parts %s"  % (line_parts,) )
        try:    doc_string = line_parts[1]
        except: doc_string = ""    
        is_doc_closed = len(line_parts) > 2  
        doc_lineno = lineno
        while not is_doc_closed:                                                            
            doc_lineno += 1                 
            try:               
                line_parts =(mod_lines[ doc_lineno ].strip()
                                .split( TRIPLE_DOUBLE ) )
                doc_string += NEW_LINE + line_parts[ 0 ]
                is_doc_closed = len(line_parts) > 1
            except: is_doc_closed = True   
        #print("extracted doc_string: %s"  % (doc_string,) )    
        return doc_string                            
    return None

_prior_import_trace_varname = None
_prior_import_trace_path = None

def __var_docstring( module, varname: str ):
    
    #print( "__var_docstring", varname )
       
    def __get_import_module_name( root_node, varname ):
        # search recursively, to handle imports being made in 
        # lower level blocks e.g. conditional imports     
        for child in ast.walk( root_node ):
            if isinstance( child, ast.ImportFrom ):               
                names = [n.asname if n.asname else n.name  
                         for n in child.names]
                if varname in names:
                    name = child.module
                    if child.level > 0:
                        # Relative import: reconstruct full dotted name
                        pkg = getattr(module, "__package__", None) or getattr(module, "__name__", "") or ""
                        parts = pkg.split(".") if pkg else []
                        # level 1 = current pkg, level 2 = parent pkg, etc.
                        parts = parts[:max(0, len(parts) - (child.level - 1))]
                        base = ".".join(parts)
                        name = (base + "." + name) if (base and name) else (base or name or "")
                    return name
        return None
      
    try: 
        mod_source = inspect.getsource( module )
        root_node = ast.parse( mod_source )
        docstring = __docstring( root_node, varname, mod_source )                        
        if docstring == False:
            module_name = __get_import_module_name( root_node, varname )
            #print( "module_name", module_name )
            if not module_name:
                # Fall back: try wildcard imports (from X import *)
                for child in ast.walk( root_node ):
                    if ( isinstance( child, ast.ImportFrom ) and
                         child.names and child.names[0].name == '*' ):
                        wname = child.module or ""
                        if child.level > 0:
                            wpkg = getattr(module, "__package__", None) or getattr(module, "__name__", "") or ""
                            wparts = wpkg.split(".") if wpkg else []
                            wparts = wparts[:max(0, len(wparts) - (child.level - 1))]
                            wbase = ".".join(wparts)
                            wname = (wbase + "." + wname) if (wbase and wname) else (wbase or wname)
                        if not wname: continue
                        try:
                            star_mod = __get_import_module( wname )
                            if star_mod and hasattr( star_mod, varname ):
                                module_name = wname
                                break
                        except: pass
            if not module_name: 
                raise RuntimeWarning("Can't find assignment or import")
                        
            #------------------------------------------------------------
            # If "failed recursion" is detected, the "escape hatch" is to  
            # try an alternate (longer, more error prone...) solution.
            global _prior_import_trace_varname, _prior_import_trace_path
            mod_filepath = __get_module_path( module_name )  
            is_failed_recurse =( varname == _prior_import_trace_varname and 
                                 mod_filepath == _prior_import_trace_path )            
            if is_failed_recurse:                                 
                #print( "failed recursive search!" )
                docstring = __var_docstring_from_source( 
                    mod_source, mod_filepath, varname )
            _prior_import_trace_varname = varname             
            _prior_import_trace_path    = mod_filepath
            if is_failed_recurse: return docstring 
            #------------------------------------------------------------
                        
            import_module = __get_import_module( module_name )            
            return __var_docstring( import_module, varname )
        else: return docstring        
    except Exception as e:
        __on_warn_exc("cannot find / parse source for variable %s" % 
                      (varname), e) 
        return None 

 
def __var_docstring_from_source( mod_source, mod_path: str, varname: str ):    
    import_details = __get_import_dtls( mod_source, mod_path )
    for imp in import_details:                            
        if ".".join(imp.name) == varname:                  
            #print( "Is it within %s?" % (imp.real_path,) )
            return __var_docstring_from_path( imp.real_path, varname )
    return False    

def __var_docstring_from_path( mod_path, varname: str ):

    def __traceImport( node, varname, mod_source, mod_path ):
        names = [n.asname if n.asname else n.name for n in node.names]
        if varname in names: 
            return __var_docstring_from_source( mod_source, mod_path, varname ) 
        else: return None
                
    #print("searching for %s docstring in %s" % (varname, mod_path) ) 
    try: 
        with open( mod_path, 'r' ) as f: mod_source=f.read()
    except Exception as e:
        __on_err_exc("cannot read from path: %s" % (mod_path,), e)
        return None 
    
    try: ast_root_node = ast.parse(  mod_source )    
    except Exception as e: 
        __on_warn_exc("failed to parse source from %s" % (mod_path,), e)
        return None

    doc_string = None
    for node in ast.walk( ast_root_node ):
        if isinstance( node, (ast.Import, ast.ImportFrom) ): 
            doc_string = __traceImport( node, varname, mod_source, mod_path )
        if isinstance( node, ast.Assign ):
            doc_string = __docstring( node, varname, mod_source ) 
        if doc_string: break            
            
    #print("%s doc_string: %s" % (varname, doc_string) )             
    return doc_string

def __get_import_dtls( file_content, file_path ):

    __MEMBER_DELIM = __SUB_MOD_DELIM = '.'            
    __IMPORT_TMPLT       = "import %s"
    __FROM_IMPORT_TMPLT  = "from %s import %s"
    __IS_MOD_TMPLT       = "inspect.ismodule( %s )"
    __GET_MOD_PATH_TMPLT = "inspect.getfile( %s )"

    ImportInfo = collections.namedtuple( "ImportInfo", [ 
        "module", "name", "alias", "lineno",
        "real_mod", "real_mbr", "real_path" 
    ]) 
            
    def __yieldImport( file_content, file_path ):
        def isMod( modName ):
            try: 
                exec( __IMPORT_TMPLT % (modName,) ) 
                return eval( __IS_MOD_TMPLT % (modName,) )
            except: return False    

        def modPath( modName, file_path, rel_import_lvl=None ):
            #print( "modPath", modName, file_path, rel_import_lvl )
            if rel_import_lvl > 0:
                source_dir_path = file_path
                for _ in range(rel_import_lvl):  
                    source_dir_path = os.path.split( source_dir_path )[0]
                path = os.path.join( source_dir_path, modName + DOT_PY_EXT )
                #print( "path?=", path ) 
                if os.path.exists( path ):
                    #print( "rel_import_lvl modPath=", path ) 
                    return path
            try: 
                exec( __IMPORT_TMPLT % (modName,) ) 
                return eval( __GET_MOD_PATH_TMPLT % (modName,) )
            except: return None     
                            
        def isChild( moduleName, childName ):
            try:
                exec( __FROM_IMPORT_TMPLT % (moduleName, childName) )
                return True
            except: return False
        
        root = ast.parse( file_content )           
        for node in ast.walk( root ):
            #print(node)
            rel_import_lvl=0
            if   isinstance( node, ast.Import ): module = []
            elif isinstance( node, ast.ImportFrom ):                                        
                try:    module = node.module.split( __SUB_MOD_DELIM )                    
                except: module = []
                rel_import_lvl = node.level                                                                    
            else: continue        
            for n in node.names:                
                name = n.name.split( __MEMBER_DELIM )                    
                real_path = None                
                real_mod = None
                real_mbr = None
                impParts = module + name
                for i in range(len( impParts )):
                    # start with the whole thing, then chop off more from 
                    # the end each time                                  
                    head = ( __MEMBER_DELIM.join( impParts ) if i==0 else
                             __MEMBER_DELIM.join( impParts[:-i] ) )
                    # start with nothing, then collect more from the end each time
                    tail = "" if i==0 else __MEMBER_DELIM.join( impParts[-i:] )
                    if isMod( head ):
                        real_mod = head                                     
                        real_path = modPath( 
                            real_mod, file_path, rel_import_lvl )
                        if isChild( real_mod, tail ): real_mbr = tail                        
                        break
                #print(module, name, n.asname, node.lineno, real_mod, real_mbr, real_path)    
                yield ImportInfo( module, name, n.asname, node.lineno,
                                  real_mod, real_mbr, real_path )
                # Execution resumes here (with the locals preserved!) 
                # on the next call to this function per the magic of "yield"...                           
        
    return [imp for imp in __yieldImport( file_content, file_path )]

def __toc_escape_magic_name( name: str ): return name.replace('__', '95')

def __html_escape_magic_name( name: str ): return name.replace('__', '&#95;&#95;')
    
def __is_magic_name( name: str ): return name.startswith('__') and name.endswith('__')

def __is_private_name( name: str ): return name.startswith('__')

def __is_protected_name( name: str ): return name.startswith('_')

def __builtin_object_member_names(): return dir(type('dummy', (object,), {}))
        
def __get_import_vars( module ): 
    #TODO: Find a more concise way to do this...
    import_vars=[]
    builtin_names=__builtin_object_member_names()
    for n,o in inspect.getmembers(module):
        if __is_protected_name(n): continue
        if __is_private_name(n): continue
        if __is_magic_name(n): continue        
        if n in builtin_names: continue        
        if inspect.isabstract(o): continue
        if inspect.isasyncgen(o): continue
        if inspect.isasyncgenfunction(o): continue
        if inspect.isawaitable(o): continue
        if inspect.isbuiltin(o): continue
        if inspect.isclass(o): continue
        if inspect.iscode(o): continue
        if inspect.iscoroutine(o): continue
        if inspect.iscoroutinefunction(o): continue
        if inspect.isdatadescriptor(o): continue
        if inspect.isframe(o): continue
        if inspect.isfunction(o): continue
        if inspect.isgenerator(o): continue
        if inspect.isgeneratorfunction(o): continue
        if inspect.isgetsetdescriptor(o): continue
        if inspect.ismemberdescriptor(o): continue
        if inspect.ismethod(o): continue
        if inspect.ismethoddescriptor(o): continue
        if inspect.ismodule(o): continue
        if inspect.isroutine(o): continue
        if inspect.istraceback(o): continue
        import_vars.append((n,o))
    return import_vars

def __write_mod( md_file, module_path: str, package_name: str, class_name: str, options ):
    try:
        module = __get_import_by_path( module_path )
        moddoc = __markdown_safe( inspect.getdoc(module) or "" )
        if moddoc:
            md_file.write(moddoc + "\n\n")
        clas  = [create_class(module, package_name, n, o, options) # 
                for n, o in inspect.getmembers(module, inspect.isclass)]
        funs  = [create_fun(n, o, options)
                for n, o in inspect.getmembers(module, inspect.isfunction)]                                        
        gvars = [create_var(n, o, o, __var_docstring(module,n), options)  
                for n, o in __get_import_vars(module)]
        for c in clas:
            write_class(md_file, c, options)
            md_file.writelines("""\n______\n\n""")
        for f in funs:
            write_function(md_file, f, options)
            md_file.writelines("""\n______\n\n""")
        for v in gvars:
            write_variable(md_file, v, options)
            md_file.writelines("""\n______\n\n""")
    except Exception as e:  
        __on_warn_exc("failed to write definition of module %s from %s" % 
                      (class_name, module_path), e)
       
def __write_class( md_file, module_path: str, class_name: str, options ):
    try:
        module = __get_import_by_path( module_path )        
        package_name = os.path.splitext(os.path.basename(module_path))[0]
        clas = __get_import_class( module, package_name, class_name, options )        
        if clas:
            write_class(md_file, clas, options)
            md_file.writelines("""\n______\n\n""")
    except Exception as e:  
        __on_warn_exc("failed to write definition of class %s from %s" % 
                      (class_name, module_path), e)
       
def __write_func( md_file, module_path: str, func_name: str, options ):
    try:
        module = __get_import_by_path( module_path )
        func = __get_import_func( module, func_name, options )        
        if func:
            write_function(md_file, func, options)
            md_file.writelines("""\n______\n\n""")
    except Exception as e: 
        __on_warn_exc("failed to write definition of function %s from %s" % 
                      (func_name, module_path), e)

def __write_var( md_file, module_path: str, var_name: str, options ):
    try:
        module = __get_import_by_path( module_path )
        var = __get_import_var( module, var_name, options )        
        if var:
            write_variable(md_file, var, options)
            md_file.writelines("""\n______\n\n""")
    except Exception as e: 
        __on_warn_exc("failed to write definition of variable %s from %s" % 
                      (var_name, module_path), e)

# process "magic virtual code comments"
def _to_virtual_lines(lines):     
    is_virtual_line=False
    v_lines=[]
    for line in lines:
        clean_line = line.strip()
        if clean_line.startswith( MAGIC_VIRTUAL_COMMENT_START ):
            #print("MAGIC_VIRTUAL_COMMENT")
            is_virtual_line=True
            continue
        if is_virtual_line and clean_line.startswith( 
            MAGIC_VIRTUAL_COMMENT_END ):
            #print("MAGIC_VIRTUAL_COMMENT_END")
            is_virtual_line=False
            continue                
        v_lines.append(line)
    return v_lines
        
def __parse_sec_for_import_names( module, all_names, package_path, snippet_lines ):   
    
    def __get_identifier_names( ast_root_node ):        
        parsed_imports=[]    
        for node in ast.walk( ast_root_node ):
            if isinstance( node, (ast.Import, ast.ImportFrom) ):               
                names = [n.asname if n.asname else n.name  
                         for n in node.names]
                parsed_imports.extend( names )
        return parsed_imports               

    # get the identifiers which are only found in the code snippet 
    sys.path.insert(0, package_path)                    
    snippet_lines  = _to_virtual_lines(snippet_lines)
    snippet_source = NEW_LINE.join(snippet_lines)                    
    try: ast_root_node = ast.parse( snippet_source )    
    except Exception as e: 
        __on_warn_exc("failed to parse source snippet from package %s" % 
                      (package_path,), e)
        sys.path.remove(package_path)
        return None
    #finally: sys.path.remove(package_path) # breaks things down stream...
    
    snippet_identifier_names = __get_identifier_names( ast_root_node )    
    #print( "snippet identifiers", snippet_identifier_names )
        
    # filter the complete lists against the subset of names from the snippet 
    mod_names, class_names, func_names, var_names = all_names
    mod_names   = [n for n in mod_names   if n in snippet_identifier_names]
    class_names = [n for n in class_names if n in snippet_identifier_names]
    func_names  = [n for n in func_names  if n in snippet_identifier_names]
    var_names   = [n for n in var_names   if n in snippet_identifier_names]

    # get the source paths for the filtered down items being returned
    mod_info={}
    for n in mod_names:   mod_info[n]   = __get_source_path( module, n )
    class_info={}
    for n in class_names: class_info[n] = __get_source_path( module, n )
    func_info={}
    for n in func_names:  func_info[n]  = __get_source_path( module, n )
    var_info={}
    for n in var_names:   var_info[n]   = __get_source_path( module, n )
                            
    return mod_info, class_info, func_info, var_info

def __docs_dir(yaml_path: str):
    docs_dir = 'docs'
    docs_dir_prefix = "docs_dir:"
    if os.path.isfile(yaml_path):            
        with open(yaml_path, "r") as f:
            for ln in f:
                if ln.strip().startswith(docs_dir_prefix):
                    docs_dir = ln.replace(docs_dir_prefix,'').strip()                     
    return docs_dir

def __prep_source( source:str ):
    return rm_docstring_from_source( make_virtual_code_real( source ) )
                    
# TODO: define this function correctly
def __markdown_safe(obj): 
    s = str(obj)
    s = set_indent( s, 0 )
    s = s.replace(MAGIC_SPACE,SPACE).replace(MAGIC_TAB,TAB)
    # double edge sword here! We'd like to remove <> that aren't
    # intended to be markdown/up elements / tags, and leave those which are.
    #s = s.replace('<','').replace('>','')
    return s 

__warn_msg="[-]Warning: {0}"
def __on_warn_exc(msg,e,is_silent=False):
    if is_silent: return    
    sys.stdout.write(__warn_msg.format(str(msg)))
    sys.stdout.write(__warn_msg.format(str(e)))
    sys.stdout.flush()
    traceback.print_exc()   

__err_msg="[-]ERROR: {0}"
def __on_err_exc(msg,e,is_silent=False):
    if not is_silent:     
        sys.stderr.write(__err_msg.format(str(msg)))
        sys.stderr.write(__err_msg.format(str(e)))
        sys.stderr.flush()
        traceback.print_exc()   
    raise e
