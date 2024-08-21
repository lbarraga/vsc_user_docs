import json
import os
import re
import shutil
import yaml
from itertools import chain
from pathlib import Path
from jinja2 import FileSystemLoader, Environment, ChoiceLoader, FunctionLoader, Template

#################### define macro's ####################
# customizable macros
MIN_PARAGRAPH_LENGTH = 128
MAX_TITLE_DEPTH = 4
INCLUDE_LINKS_IN_PLAINTEXT = True

# directories
PARSED_MDS = "parsed_mds"
COPIES = "copies"
IF_MANGLED_FILES = "if_mangled_files"
LINUX_TUTORIAL = "linux-tutorial"
RETURN_DIR = ".."
MKDOCS_DIR = "mkdocs"
DOCS_DIR = "docs"
HPC_DIR = "HPC"
EXTRA_DIR = "extra"
GENERIC_DIR = "generic"
OS_SPECIFIC_DIR = "os_specific"

# OSes
LINUX = "linux"
WINDOWS = "windows"
MACOS = "macos"
GENERIC = "generic"

# urls
REPO_URL = 'https://github.com/hpcugent/vsc_user_docs'
DOCS_URL = "https://docs.hpc.ugent.be"

# OS-related if-states
ACTIVE = "active"
INACTIVE = "inactive"

# if mangler states
NON_OS_IF = 0
NON_OS_IF_IN_OS_IF = 1
OS_IF = 2
OS_IF_IN_OS_IF = 3

# if mangler macros
IF_MANGLED_PART = "-if-"

# actions
DONE = "done"
WRITE_TEXT = "write_text"
CHECK_EXTRA_MESSAGE = "check_extra_message"
WRITE_TEXT_AND_CHECK_EXTRA_MESSAGE = "write_text_and_check_extra_message"

# JSON attributes
CONTENT = "content"
LINKS = "links"
REFERENCE_LINK = "reference_link"


################### define functions ###################
def check_for_title_xl(curr_line, main_title, last_directory, last_title, curr_dirs, root_dirs, link_lists, is_linux_tutorial_, in_code_block_):
    """
    function that uses the check_for_title_logic function to create the appropriate directories and update the necessary variables

    :param curr_line: the line to be checked for a title
    :param main_title: the main title of the file, needed in the case where a file is finished
    :param last_directory: the most recently encountered directory
    :param last_title: the most recently encountered title
    :param curr_dirs: the most recent directories at each title level
    :param root_dirs: a list containing the root directories
    :param link_lists: a list containing all four link_lists with the links that will be printed at the bottom of a file
    :param is_linux_tutorial_: boolean to indicate whether the current file is part of the linux tutorial
    :param in_code_block_: boolean to indicate whether the current line is part of a codeblock
    :return: the depth of the title
    :return: the title found in the line if any
    :return: the new directory in which the next file will be written
    :return link_lists: updated link_lists
    """

    # detect titles
    match = re.match(r'^#+ ', curr_line)
    if match and len(match.group(0)) <= MAX_TITLE_DEPTH + 1:
        logic_output = len(match.group(0)) - 1
    else:
        logic_output = 0

    # make necessary changes if a title has been detected
    if logic_output == 0 or in_code_block_:
        return 0, None, None, curr_dirs, link_lists
    else:

        # if a new title is detected, write the end of the previous file
        if last_title is not None:
            for i, OS in enumerate(["", "Linux", "Windows", "macOS"]):
                write_end_of_file(os.path.join(root_dirs[i], last_directory, last_title + ".json"), OS, link_lists[i], is_linux_tutorial_, main_title, last_title)

            # reset the link lists for each OS
            for i in range(4):
                link_lists[i] = []

        # make a new directory corresponding with the new title
        curr_dirs[logic_output] = os.path.join(curr_dirs[logic_output - 1], make_valid_title(curr_line[logic_output + 1:-1].replace(' ', '-')))

        for i in range(4):
            os.makedirs(os.path.join(root_dirs[i],  curr_dirs[logic_output]), exist_ok=True)

        # update the higher order current directories
        for i in range(logic_output + 1, MAX_TITLE_DEPTH + 1):
            curr_dirs[i] = curr_dirs[logic_output]

        return logic_output, make_valid_title(curr_line[logic_output + 1:-1].replace(' ', '-')), curr_dirs[logic_output], curr_dirs, link_lists


def check_for_title(line, in_code_block, curr_dirs):
    """
    function that checks for titles in the current line. Used by split_text to split the text among the subtitles

    :param line: the current line to be checked for a title
    :param in_code_block: boolean indicating whether the current line is part of a codeblock to be sure comments aren't counted as titles
    :param curr_dirs: the current working directories for each level of subtitle, to be updated when a new title is found
    :return title_length: The amount of hashtags in front of the title on the current line
    """
    # detect titles
    match = re.match(r'^#+ ', line)
    if match and len(match.group(0)) <= 5 and not in_code_block:
        title_length = len(match.group(0)) - 1
        curr_dirs[title_length] = os.path.join(curr_dirs[title_length - 1], make_valid_title(line[title_length + 1:-1].replace(' ', '-')))

        # update the higher order current directories
        for i in range(title_length + 1, MAX_TITLE_DEPTH + 1):
            curr_dirs[i] = curr_dirs[title_length]

        return title_length
    else:
        return 0


def replace_markdown_markers(curr_line, linklist, in_code_block, main_title):
    """
    function that replaces certain markdown structures with the equivalent used on the website

    :param curr_line: the current line on which markdown structures need to be replaced
    :param linklist: the list used to store links that need to be printed at the end of the file
    :param in_code_block: boolean indicating whether the current line is part of a code block
    :param main_title: the main title of the file that is being processed
    :return curr_line: the adapted current line
    :return linklist: the updated linklist
    """

    # replace images with an empty line
    if re.search(r'(?i)!\[image]\(.*?\)', curr_line) or re.search(r'!\[]\(img/.*?.png\)', curr_line):
        curr_line = ""

    # replace links with a reference
    matches = re.findall(r'\[(.*?)]\((.*?)\)', curr_line)
    if matches:
        for match in matches:
            curr_line = curr_line.replace(f"[{match[0]}]({match[1]})", match[0] + "[" + str(len(linklist) + 1) + "]")
            if ".md" not in match[1]:
                if "#" not in match[1]:
                    linklist.append(match[1])
                else:
                    linklist.append(DOCS_URL + main_title + "/" + match[1])
            else:
                linklist.append(DOCS_URL + match[1].replace(".md", "/").replace("index", "").rstrip("/"))

    # codeblock (with ``` -> always stands on a separate line, so line can be dropped)
    if '```' in curr_line:
        curr_line = ""

    # structures within <>
    match = re.findall(r'<(.*?)>', curr_line)
    if match:
        for i, content in enumerate(match):
            syntax_words = ["pre", "b", "code", "sub", "br", "center", "p", "div", "u", "p", "i", "tt", "a", "t", "span"]  # make sure these are always lowercase
            syntax_words_variations = list(chain.from_iterable([[element, element + "/", "/" + element] for element in syntax_words]))
            syntax_words_style = [element + " style=.*" for element in syntax_words]

            # add references for every link of format <a href=...>
            if re.search(r'a href=.*', content):
                link = content[8:-1]
                curr_line = re.sub(f'<{content}>', "[" + str(len(linklist) + 1) + "]", curr_line)
                linklist.append(link)

            # drop the syntax words
            elif content.lower() in syntax_words_variations:
                curr_line = re.sub(f'<{content}>', "", curr_line)

            # drop the version of the syntax_words followed by " style="
            elif any(re.match(pattern, content) for pattern in syntax_words_style):
                curr_line = re.sub(r'<.*?>', "", curr_line)

            # drop markdown comments
            elif re.fullmatch(r'!--.*?--', content):
                curr_line = re.sub(r'<.*?>', "", curr_line)

            # special case (ugly fix)
            elif ' files</b' in content:
                curr_line = re.sub(r'</b>', "", curr_line)

            # keep the rest
            else:
                pass

    # structures with !!! (info, tips, warnings)
    if '!!!' in curr_line:
        curr_line = re.sub(r'!!!', "", curr_line)

    # structures with ??? (collapsable admonitions)
    if '???' in curr_line:
        curr_line = re.sub(r'\?\?\?', "", curr_line)

    # get rid of other markdown indicators (`, *, +, _)
    if not in_code_block:

        backquotes = re.findall(r'`(.*?)`', curr_line)
        if backquotes:
            for i, content in enumerate(backquotes):
                curr_line = curr_line.replace(f"`{content}`", content)

        asterisks = re.findall(r'(?<!\\)(\*+)(.+?)\1', curr_line)
        if asterisks:
            for i, content in enumerate(asterisks):
                curr_line = re.sub(r"(\*+)" + content[1] + r"\1", content[1], curr_line)

        pluses = re.findall(r'\+\+(.+?)\+\+', curr_line)
        if pluses:
            for i, content in enumerate(pluses):
                curr_line = re.sub(r"\+\+" + content + r"\+\+", content, curr_line)

        underscores = re.findall(r' (_+)(.+?)\1 ', curr_line)
        if underscores:
            for i, content in enumerate(underscores):
                curr_line = re.sub(r"(_+)" + content[1] + r"\1", content[1], curr_line)

    return curr_line, linklist


def split_text(file, main_title):
    """
    Function that splits the text into smaller sections and makes them into two dictionaries containing text and metadata
    :param file: the filepath of the file to be split
    :param main_title: the main title of the file
    :return paragraphs_text: dictionary containing the split sections of text
    :return paragraphs_metadata: dictionary containing the metadata of each split section of text
    :return subtitle_order: list containing all encountered subtitles in order of appearance
    """

    # start of assuming we haven't encountered a title
    after_first_title = False

    # start of assuming we are not in a code_block
    in_code_block = False

    # define initial dictionaries
    paragraphs_text = {}
    paragraphs_metadata = {}

    # list to keep track of links in the text
    link_list = []

    # list to keep track of the order of the subtitles
    subtitle_order = []

    # variable to keep track of the title level
    title_level = 0

    # variable to allow for if statements to "continue" over multiple paragraphs
    open_ifs = ""

    # list to keep track of most recent directories on each title level
    if LINUX_TUTORIAL not in file:
        curr_dirs = [main_title for _ in range(MAX_TITLE_DEPTH + 1)]
    else:
        curr_dirs = [os.path.join(LINUX_TUTORIAL, main_title) for _ in range(MAX_TITLE_DEPTH + 1)]

    with open(file, 'r') as readfile:

        for line in readfile:

            # keep track of title level and directory to write to metadata upon discovering a new subtitle
            if title_level > 0:
                last_title_level = title_level
                last_dir = curr_dirs[last_title_level]

            title_level = check_for_title(line, in_code_block, curr_dirs)

            # detect codeblocks to make sure titles aren't detected in them
            if '```' in line or (('<pre><code>' in line) ^ ('</code></pre>' in line)):
                in_code_block = not in_code_block

            # line is a title with a maximum depth of 4
            if title_level > 0:
                if after_first_title:
                    paragraphs_text[title], open_ifs = close_ifs(paragraphs_text[title])
                    paragraphs_metadata[title] = write_metadata(main_title, title, link_list, last_title_level, last_dir)
                title = make_valid_title(line[title_level + 1:-1])

                # create an entry for the file in the paragraphs text dictionary
                paragraphs_text[title] = open_ifs

                after_first_title = True
                subtitle_order.append(title)

                # reset link_list
                link_list = []

            # line is not a title
            elif after_first_title:
                line, link_list = replace_markdown_markers(line, link_list, in_code_block, main_title)
                if title in paragraphs_text.keys() and line != "\n":
                    paragraphs_text[title] += line
                elif line != "\n":
                    paragraphs_text[title] = line

    # write metadata for the last file
    paragraphs_metadata[title] = write_metadata(main_title, title, link_list, title_level, curr_dirs[last_title_level])

    return paragraphs_text, paragraphs_metadata, subtitle_order


def write_metadata(main_title, subtitle, links, title_level, directory):
    """
    Function that writes metadata about a text section to a dictionary

    :param main_title: The main title of the file containing the section
    :param subtitle: the title of the section
    :param links: a list of links contained within the section
    :param title_level: the depth of the title of the section
    :param directory: the directory where the section will eventually be written (can either be generic or os-specific)
    :return paragraph_metadata: dictionary containing the metadata about the section
    """

    paragraph_metadata = {'main_title': main_title, 'subtitle': subtitle, 'title_depth': title_level, 'directory': directory}

    if len(links) > 0:
        paragraph_metadata['links'] = {}
        for i, link in enumerate(links):
            paragraph_metadata['links'][str(i)] = link

    paragraph_metadata['parent_title'] = Path(directory).parent.name

    return paragraph_metadata


def close_ifs(text):
    """
    Function to check whether all if-statements in a section are closed properly. If that is not the case, the function
    closes all if-statements at the end of the section and returns a prefix for the next section containing all if-statements
    of the section it is processing. This needs to be done because the start of the next section would also be contained within the
    last unclosed if-statement of its previous section.

    :param text: the text of the section it checks
    :return text: the adapted text where all if-statements are closed
    :return prefix: the prefix for the next section
    """

    patterns = {
        'if': r'({' + IF_MANGLED_PART + r'%[-\s]*if\s+OS\s*[!=]=\s*.+?[-\s]*%' + IF_MANGLED_PART + '})',
        'endif': r'({' + IF_MANGLED_PART + r'%\s*-?\s*endif\s*-?\s*%' + IF_MANGLED_PART + '})',
        'else': r'({' + IF_MANGLED_PART + r'%\s*-?\s*else\s*-?\s*%' + IF_MANGLED_PART + '})'
    }
    if_count = len(re.findall(patterns['if'], text.replace("\n", "")))
    endif_count = len(re.findall(patterns['endif'], text.replace("\n", "")))
    if IF_MANGLED_PART not in text or if_count == endif_count:
        return text, ""
    else:

        # Find all matches for each pattern
        matches = []
        for key, pattern in patterns.items():
            for match in re.finditer(pattern, text):
                matches.append(match)

        # sort the matches according to their start index
        matches.sort(key=lambda x: x.start())

        # extract the strings from the matches
        open_ifs = []
        for match in matches:
            open_ifs.append(match.group(0))

        # Concatenate all matches into a single string
        open_ifs = ''.join(open_ifs)

        return text + r'{' + IF_MANGLED_PART + '% endif %' + IF_MANGLED_PART + '}', open_ifs


def jinja_parser(filename, copy_location):
    """
    function that let's jinja do its thing to format the files except for the os-related if-statements

    :param filename: the name of the file that needs to be formatted using jinja
    :param copy_location: the location of the file that needs to be formatted using jinja
    :return:
    """
    # YAML file location
    yml_file_path = os.path.join(RETURN_DIR, RETURN_DIR, MKDOCS_DIR, EXTRA_DIR, 'gent.yml')

    # Read the YAML file
    with open(yml_file_path, 'r') as yml_file:
        words_dict = yaml.safe_load(yml_file)

    # ugly fix for index.md error that occurs because of the macro "config.repo_url" in mkdocs/docs/HPC/index.md
    additional_context = {
        'config': {
            'repo_url': REPO_URL
        }
    }
    combined_context = {**words_dict, **additional_context}

    # Mangle the OS-related if-statements
    mangle_ifs(copy_location, filename)

    # Use Jinja2 to replace the macros
    template_loader = ChoiceLoader([FileSystemLoader(searchpath=[IF_MANGLED_FILES, os.path.join(RETURN_DIR, RETURN_DIR, MKDOCS_DIR, DOCS_DIR, HPC_DIR)]), FunctionLoader(load_macros)])
    templateEnv = Environment(loader=template_loader)
    template = templateEnv.get_template(filename)
    rendered_content = template.render(combined_context)

    # Save the rendered content to a new file
    with open(copy_location, 'w', encoding='utf-8', errors='ignore') as output_file:
        output_file.write(rendered_content)


def load_macros(name):
    """
    function used by the jinja FunctionLoader to retrieve templates from the macros folder since the normal FileSystemLoader can't locate them properly

    :param name: name of the package
    :return:
    """

    macros_location = os.path.join(RETURN_DIR, RETURN_DIR, MKDOCS_DIR, DOCS_DIR, "macros")

    if "../macros/" in name:
        package_name = name.split("../macros/")[1]
        file_location = os.path.join(macros_location, package_name)

        with open(file_location, 'r') as readfile:
            return readfile.read()


def mangle_os_ifs(line, is_os):
    """
    function that mangles the os-related if-statements. This is needed because we want to keep these if-statements intact after jinja-parsing to build the directory structure.
    We don't want to mangle all if-related statements (such as else and endif) so we need to keep track of the context of the last few if-statements.

    :param line: the current line to check for os-related if-statements
    :param is_os: variable keep track of the current os-state of the if-statements. Can be NON_OS_IF, NON_OS_IF_IN_OS_IF, OS_IF or OS_IF_IN_OS_IF 
        NON_OS_IF: not in an os-if
        NON_OS_IF_IN_OS_IF: in a non-os-if nested in an os-if
        OS_IF: in an os-if
        OS_IF_IN_OS_IF: in an os-if nested in an os-if
    :return line: the modified line with  mangled os-related if-statements
    """

    match = re.search(r'\{%(.*?)%}(.*)', line)

    start_index = 0
    added_length = 0

    while match:

        constr_match = re.search(r'\{%.*?%}', match.string)
        if_match = re.search(r'if ', match.group(1))
        if_os_match = re.search(r'if OS ', match.group(1))
        endif_match = re.search(r'endif', match.group(1))
        else_match = re.search(r'else', match.group(1))

        # mangle positions
        pos_first_mangle = constr_match.start() + start_index + added_length + 1
        pos_second_mangle = constr_match.end() + start_index + added_length - 1

        # different parts of the original string
        part_before_mangling = line[:pos_first_mangle]
        part_between_mangling = line[pos_first_mangle:pos_second_mangle]
        part_after_mangling = line[pos_second_mangle:]

        # this logic isn't flawless, there are number of nested if-constructions that are technically possible that would break this logic, but these don't appear in the documentation as it doesn't make sense to have these
        if endif_match:
            if is_os in (OS_IF, OS_IF_IN_OS_IF):
                line = part_before_mangling + IF_MANGLED_PART + part_between_mangling + IF_MANGLED_PART + part_after_mangling
                added_length += 2 * len(IF_MANGLED_PART)
                if is_os == OS_IF:
                    is_os = NON_OS_IF
                elif is_os == OS_IF_IN_OS_IF:
                    is_os = OS_IF
            elif is_os == NON_OS_IF_IN_OS_IF:
                is_os = OS_IF
                
        elif if_match:
            if if_os_match:
                line = part_before_mangling + IF_MANGLED_PART + part_between_mangling + IF_MANGLED_PART + part_after_mangling
                added_length += 2 * len(IF_MANGLED_PART)
                if is_os == OS_IF:
                    is_os = OS_IF_IN_OS_IF
                else:
                    is_os = OS_IF
            else:
                if is_os == OS_IF:
                    is_os = NON_OS_IF_IN_OS_IF
                else:
                    is_os = NON_OS_IF
                    
        elif else_match:
            if is_os in (OS_IF, OS_IF_IN_OS_IF):
                line = part_before_mangling + IF_MANGLED_PART + part_between_mangling + IF_MANGLED_PART + part_after_mangling
                added_length += 2 * len(IF_MANGLED_PART)

        start_index += constr_match.end()
        match = re.search(r'\{%(.*?)%}(.*)', match.group(2))
    return line, is_os


def mangle_ifs(directory, filename):
    """
    function that writes the if-mangled version of a file to a location where the jinja parser will use it

    :param directory: the directory of the file to be if mangled
    :param filename: the filename of the file to be mangled
    :return:
    """
    # variable to keep track of latest if-statement scope
    is_os = NON_OS_IF

    with open(os.path.join(IF_MANGLED_FILES,  filename), 'w') as write_file:
        with open(directory, 'r') as read_file:
            for line in read_file:
                new_line, is_os = mangle_os_ifs(line, is_os)
                write_file.write(new_line)


def check_if_statements(curr_line, active_OS_if_states):
    """
    function that checks for if-statements

    :param curr_line: the line to be checked for if-statements to build the directory structure
    :param active_OS_if_states: dictionary keeping track of the active OS states according to the if-statements
    :return: the next action to be done with the line:
                DONE: An if-statement has been found at the start of the line, the active os list has been updated, processing of the current line is finished and a following line can be processed.
                CHECK_EXTRA_MESSAGE: An if-statement has been found at the start of the line, the active os list has been updated, more text has been detected after the if-statement that also needs to be checked.
                WRITE_TEXT: No if-statement has been found, write the current line to a file (can also be part of the current line)
                WRITE_TEXT_AND_CHECK_EXTRA_MESSAGE: An if statement has been found not at the start of the line. Firstly, write the text up until the if-statement to a file, then check the rest of the line.
    :return: the extra message to be checked, if any
    :return: the text to be written to the file, if any
    """
    # check whether the first part of the line contains information wrt if-statements
    match = re.search(r'^\{' + IF_MANGLED_PART + '%(.*?)%' + IF_MANGLED_PART + '}(.*)', curr_line)

    # check whether the line contains information wrt if-statements that is not in its first part
    match_large = re.search(r'^(.*)(\{' + IF_MANGLED_PART + '%.*?%' + IF_MANGLED_PART + '})(.*)', curr_line)

    if match:
        content = match.group(1)

        # new if-statement wrt OS with '=='
        if re.search(r'if OS == ', content):
            OS = content.split()[-1]

            # set new active OS
            active_OS_if_states[OS] = ACTIVE

            # set other active ones on inactive
            for other_OS in active_OS_if_states.keys():
                if other_OS != OS and active_OS_if_states[other_OS] == ACTIVE:
                    active_OS_if_states[other_OS] = INACTIVE

        # new if-statement wrt OS with '!='
        elif re.search(r'if OS != ', content):
            OS = content.split()[-1]

            # set new active OS
            active_OS_if_states[OS] = INACTIVE

            # set other inactive ones on active
            for other_OS in active_OS_if_states.keys():
                if other_OS != OS and active_OS_if_states[other_OS] == INACTIVE:
                    active_OS_if_states[other_OS] = ACTIVE

        # endif statement wrt OS
        elif re.search(r'endif', content):
            if str(1) in active_OS_if_states.values():
                active_OS_if_states[
                    list(active_OS_if_states.keys())[list(active_OS_if_states.values()).index(str(1))]] = ACTIVE
            else:
                for key in active_OS_if_states.keys():
                    active_OS_if_states[key] = INACTIVE

        # else statement wrt OS
        elif re.search(r'else', content):

            i = 0
            for i in range(3):
                if str(i) not in active_OS_if_states.values():
                    break

            # set the previously active one on inactive until the next endif
            key_list = list(active_OS_if_states.keys())
            position = list(active_OS_if_states.values()).index(ACTIVE)
            active_OS_if_states[key_list[position]] = str(i)

            # set inactive ones on active
            while INACTIVE in active_OS_if_states.values():
                position = list(active_OS_if_states.values()).index(INACTIVE)
                active_OS_if_states[key_list[position]] = ACTIVE

        if len(match.group(2)) != 0:
            extra_message = match.group(2).lstrip()
            return CHECK_EXTRA_MESSAGE, extra_message, None

        else:
            return DONE, None, None

    elif match_large:
        return WRITE_TEXT_AND_CHECK_EXTRA_MESSAGE, match_large.group(2), match_large.group(1)

    else:
        return WRITE_TEXT, None, curr_line


def write_text_to_file(file_name, curr_line, link_lists, in_code_block):
    """
    function that writes a line to a file

    :param file_name: target file to write the line to
    :param curr_line: line to be written to the file
    :param link_lists: list containing all the links that will be printed at the end of files
    :param in_code_block: boolean indicating whether the current line is in a codeblock
    :return link_lists: updated link_lists
    """

    if os.path.exists(file_name) or curr_line.strip():
        if os.path.exists(file_name):
            with open(file_name, "r") as read_file:
                data = json.load(read_file)
        else:
            data = {}

        os_list = [GENERIC_DIR, LINUX, WINDOWS, MACOS]
        for i, os_ in enumerate(os_list):
            if os_ in file_name:
                curr_line, link_lists[i] = replace_markdown_markers(curr_line, link_lists[i], in_code_block, "placeholder")

        if CONTENT in data:
            data[CONTENT] += curr_line
        else:
            data[CONTENT] = curr_line

        with open(file_name, "w") as write_file:
            json.dump(data, write_file, indent=4)

    return link_lists


def choose_and_write_to_file(curr_line, active_OS_if_states, last_directory, last_title, root_dirs, link_lists, in_code_block):
    """
    function that decides what file to write text to

    :param curr_line: line to be written to a file
    :param active_OS_if_states: dictionary keeping track of which OSes are active according to the if-statements
    :param last_directory: most recently made directory
    :param last_title: the most recently encountered title
    :param root_dirs: a list with all root directories
    :param link_lists: list of links that need to be written at the end of the files
    :param in_code_block: boolean indicating whether the current line is in a code block
    :return link_lists: an updated link_lists
    """
    # check that the line is part of the website for gent
    if active_OS_if_states[LINUX] == INACTIVE and active_OS_if_states[WINDOWS] == INACTIVE and active_OS_if_states[MACOS] == INACTIVE:
        link_lists = write_text_to_file(os.path.join(root_dirs[0], last_directory, last_title + ".json"), curr_line, link_lists, in_code_block)
    else:
        for i, os_ in enumerate([LINUX, WINDOWS, MACOS]):
            if active_OS_if_states[os_] == ACTIVE:
                link_lists = write_text_to_file(os.path.join(root_dirs[i + 1], last_directory, last_title + ".json"),
                                                curr_line, link_lists, in_code_block)

    return link_lists


def write_end_of_file(file_location, OS, linklist, is_linux_tutorial_, main_title, last_title):
    """
    function that adds the links that should be at the end of a file

    :param file_location: the location of the file
    :param OS: the OS of the file
    :param linklist: the links that should be at the end of the file
    :param is_linux_tutorial_: boolean indicating whether the file is part of the linux tutorial
    :param main_title: the main title of the file, to be used in the reference link
    :param last_title: the most recently encountered title
    :return:
    """

    if os.path.exists(file_location):

        if len(OS) > 0:
            OS = OS + "/"

        with open(file_location, "r") as read_file:
            data = json.load(read_file)

        # add the links from within the document
        data[LINKS] = {}
        for i, link in enumerate(linklist):
            data[LINKS][str(i + 1)] = str(link)

        if is_linux_tutorial_:
            linux_part = LINUX_TUTORIAL + "/"
        else:
            linux_part = ""

        # add the reference link
        data[REFERENCE_LINK] = (DOCS_URL + "/" + OS + linux_part + main_title + "/#" + ''.join(char.lower() for char in last_title if char.isalnum() or char == '-').strip('-'))

        with open(file_location, 'w') as write_file:
            json.dump(data, write_file, indent=4)


def make_valid_title(title):
    """
    function that makes sure all titles can be used as valid filenames

    :param title: the string that will be used as title and filename
    :return valid_filename: the adapted title that can be used as filename
    """
    # Define a regex pattern for invalid characters on both Windows and Linux
    invalid_chars = r'[<>:"/\\|?*\0()]'

    # get rid of extra information between {} brackets
    title = re.sub(r'\{.*?}', '', title)

    # Remove invalid characters
    valid_filename = re.sub(invalid_chars, '', title)

    # Strip leading/trailing whitespace
    valid_filename = valid_filename.strip().strip('-')

    return valid_filename


def write_generic_file(title, paragraphs_text, paragraphs_metadata, title_order, title_order_number):
    """
    Function that writes text and metadata of a generic (non-os-specific) file

    :param title: title of section
    :param paragraphs_text: dictionary containing all paragraphs of text
    :param paragraphs_metadata: dictionary containing the metadata for all paragraphs of text
    :param title_order: list containing all subtitles in order
    :param title_order_number: order number of the title of the section that is being written
    :return:
    """

    # make the directory needed for the files that will be written
    filepath = os.path.join(PARSED_MDS, GENERIC_DIR, paragraphs_metadata[title]["directory"])
    os.makedirs(filepath, exist_ok=True)

    write_files(title, paragraphs_text[title], paragraphs_metadata, title_order, title_order_number, filepath, OS=GENERIC)


def write_os_specific_file(title, paragraphs_text, paragraphs_metadata, title_order, title_order_number):
    """
    Function that writes text and metadata of os-specific files

    :param title: title of section
    :param paragraphs_text: dictionary containing all paragraphs of text
    :param paragraphs_metadata: dictionary containing the metadata for all paragraphs of text
    :param title_order: list containing all subtitles in order
    :param title_order_number: order number of the title of the section that is being written
    :return:
    """
    for i, OS in enumerate([LINUX, WINDOWS, MACOS]):

        # Unmangle if's to use jinja parser
        paragraphs_text[title] = re.sub(IF_MANGLED_PART, "", paragraphs_text[title])

        # Use jinja to render a different version of the text for each OS
        template = Template(paragraphs_text[title])
        text = template.render(OS=OS)

        # define the filepath
        filepath = os.path.join(PARSED_MDS, OS_SPECIFIC_DIR, OS, paragraphs_metadata[title]["directory"])
        os.makedirs(filepath, exist_ok=True)

        # write the files
        write_files(title, text, paragraphs_metadata, title_order, title_order_number, filepath, OS)


def write_files(title, text, paragraphs_metadata, title_order, title_order_number, filepath, OS):
    """
    Function to write files to a certain filepath

    :param title: title of the section to be written
    :param text: section of text to be written
    :param paragraphs_metadata: dictionary containing the metadata for all paragraphs of text
    :param title_order: list containing all subtitles in order
    :param title_order_number: order number of the title of the section that is being written
    :param filepath: filepath to write files to
    :param OS: OS to be included in the metadata
    :return:
    """

    # write text file
    with open(os.path.join(filepath, paragraphs_metadata[title]["subtitle"] + ".txt"), 'w') as writefile:
        writefile.write(text)

    # write metadata
    metadata = paragraphs_metadata[title]

    if title_order_number != 0:
        metadata["previous_title"] = title_order[title_order_number - 1]
    else:
        metadata["previous_title"] = None

    if title_order_number != len(title_order) - 1:
        metadata["next_title"] = title_order[title_order_number + 1]
    else:
        metadata["next_title"] = None

    metadata["OS"] = OS

    if bool(LINUX_TUTORIAL in paragraphs_metadata[title]["directory"]):
        linux_part = LINUX_TUTORIAL + "/"
    else:
        linux_part = ""
    if OS == GENERIC:
        os_part = ""
    else:
        os_part = OS + "/"
    metadata["reference_link"] = DOCS_URL + "/" + os_part + linux_part + paragraphs_metadata[title]["main_title"] + "/#" + ''.join(char.lower() for char in title if char.isalnum() or char == '-').strip('-')

    with open(os.path.join(filepath, paragraphs_metadata[title]["subtitle"] + "_metadata.json"), 'w') as writefile:
        json.dump(metadata, writefile, indent=4)

def main():
    """
    main function
    :return:
    """
    # remove the directories from a previous run of the parser if they weren't cleaned up properly for some reason
    shutil.rmtree(PARSED_MDS)
    shutil.rmtree(COPIES)
    shutil.rmtree(IF_MANGLED_FILES)

    # make the necessary directories
    if not os.path.exists(COPIES):
        os.mkdir(COPIES)

    if not os.path.exists(os.path.join(COPIES, LINUX_TUTORIAL)):
        os.mkdir(os.path.join(COPIES, LINUX_TUTORIAL))

    if not os.path.exists(PARSED_MDS):
        os.mkdir(PARSED_MDS)

    if not os.path.exists(IF_MANGLED_FILES):
        os.mkdir(IF_MANGLED_FILES)

    ################### define loop-invariant variables ###################

    # variable that keeps track of the source directories
    source_directories = [os.path.join(RETURN_DIR, RETURN_DIR, MKDOCS_DIR, DOCS_DIR, HPC_DIR),
                          os.path.join(RETURN_DIR, RETURN_DIR, MKDOCS_DIR, DOCS_DIR, HPC_DIR, LINUX_TUTORIAL)]

    # list of all the filenames
    filenames_generic = {}
    filenames_linux = {}
    for source_directory in source_directories:
        all_items = os.listdir(source_directory)
        files = [f for f in all_items if os.path.isfile(os.path.join(source_directory, f)) and ".md" in f[-3:]]
        for file in files:
            if LINUX_TUTORIAL in source_directory:
                filenames_linux[file] = os.path.join(source_directory, file)
            else:
                filenames_generic[file] = os.path.join(source_directory, file)

    # # Temporary variables to test with just one singular file
    # filenames_generic = {}
    # filenames_linux = {}
    # filenames_generic["getting_started.md"] = "C:/HPC_werk/Documentation/local/vsc_user_docs/mkdocs/docs/HPC/getting_started.md"
    # filenames_linux["beyond_the_basics.md"] = "C:/HPC_werk/Documentation/local/vsc_user_docs/mkdocs/docs/HPC/linux-tutorial/beyond_the_basics.md"

    # for loops over all files
    for filenames in [filenames_generic, filenames_linux]:
        for filename in filenames.keys():
            ################### define/reset loop specific variables ###################

            # variable that keeps track of whether file is part of the linux tutorial
            is_linux_tutorial = bool(LINUX_TUTORIAL in filenames[filename])

            # make a copy of the original file in order to make sure the original does not get altered
            if is_linux_tutorial:
                copy_file = os.path.join(COPIES, LINUX_TUTORIAL,  filename)
            else:
                copy_file = os.path.join(COPIES, filename)
            shutil.copyfile(filenames[filename], copy_file)

            # variable that keeps track of the directories that are used to write in at different levels
            if is_linux_tutorial:
                root_dir_generic = os.path.join(PARSED_MDS, GENERIC_DIR, LINUX_TUTORIAL)
                root_dir_os_specific_linux = os.path.join(PARSED_MDS, OS_SPECIFIC_DIR, LINUX, LINUX_TUTORIAL)
                root_dir_os_specific_windows = os.path.join(PARSED_MDS, OS_SPECIFIC_DIR, WINDOWS, LINUX_TUTORIAL)
                root_dir_os_specific_macos = os.path.join(PARSED_MDS, OS_SPECIFIC_DIR, MACOS, LINUX_TUTORIAL)
            else:
                root_dir_generic = os.path.join(PARSED_MDS, GENERIC_DIR)
                root_dir_os_specific_linux = os.path.join(PARSED_MDS, OS_SPECIFIC_DIR, LINUX)
                root_dir_os_specific_windows = os.path.join(PARSED_MDS, OS_SPECIFIC_DIR, WINDOWS)
                root_dir_os_specific_macos = os.path.join(PARSED_MDS, OS_SPECIFIC_DIR, MACOS)
            root_dirs = [root_dir_generic, root_dir_os_specific_linux, root_dir_os_specific_windows, root_dir_os_specific_macos]

            # variable for the main title (needed for reference links)
            main_title = filename[:-3]

            # variable that keeps track of the directories that are used to write in at different levels
            curr_dirs = [filename[:-3] for _ in range(5)]

            # variable that keeps track of the latest non-zero level title and corresponding directory
            last_title = None
            last_directory = None

            # list to keep track of links in the text
            links_generic = []
            links_linux = []
            links_windows = []
            links_macos = []
            link_lists = [links_generic, links_linux, links_windows, links_macos]

            # dictionaries to keep track of current OS
            active_OS_if_states = {LINUX: INACTIVE, WINDOWS: INACTIVE, MACOS: INACTIVE}

            # dictionaries to save the paragraphs and metadata before it is written to files
            paragraphs_text = {}
            paragraphs_metadata = {}

            # variable that shows whether the first title has been reached yet
            after_first_title = False

            # variable that is used to be sure that we are detecting titles and not comments from codeblocks
            in_code_block = False

            ################### actually parse the md file ###################

            # create directories for the source markdown file
            for directory in [root_dir_generic, os.path.join(PARSED_MDS, OS_SPECIFIC_DIR), root_dir_os_specific_linux, root_dir_os_specific_windows, root_dir_os_specific_macos, os.path.join(root_dir_generic, curr_dirs[0]), os.path.join(root_dir_os_specific_linux, curr_dirs[0]), os.path.join(root_dir_os_specific_windows, curr_dirs[0]), os.path.join(root_dir_os_specific_macos, curr_dirs[0])]:
                os.makedirs(directory, exist_ok=True)

            # process the jinja macros
            jinja_parser(filename, copy_file)

            # split the text in paragraphs
            paragraphs_text, paragraphs_metadata, subtitle_order = split_text(copy_file, main_title)

            # for every section, either make the whole section generic, or create an os-specific file for each OS
            for i, subtitle in enumerate(subtitle_order):
                # print(subtitle)

                # generic
                if IF_MANGLED_PART not in paragraphs_text[subtitle]:
                    write_generic_file(subtitle, paragraphs_text, paragraphs_metadata, subtitle_order, i)

                # os-specific
                else:
                    write_os_specific_file(subtitle, paragraphs_text, paragraphs_metadata, subtitle_order, i)

            # # open the file and store line by line in the right file
            # with open(copy_file, 'r') as readfile:
            #
            #     for line in readfile:
            #         title_level, title, directory, curr_dirs, link_lists = check_for_title_xl(line, main_title, last_directory, last_title, curr_dirs, [root_dir_generic, root_dir_os_specific_linux, root_dir_os_specific_windows, root_dir_os_specific_macos], link_lists, is_linux_tutorial, in_code_block)
            #
            #         # detect codeblocks to make sure titles aren't detected in them
            #         if '```' in line or (('<pre><code>' in line) ^ ('</code></pre>' in line)):
            #             in_code_block = not in_code_block
            #
            #         # line is a title with a maximum depth of 4
            #         if title_level > 0:
            #             last_title = title
            #             last_directory = directory
            #             after_first_title = True
            #
            #         # line is not a title
            #         elif after_first_title:
            #             # check for if-statements and write the appropriate lines in the right files
            #             next_action = check_if_statements(line, active_OS_if_states)
            #             while next_action[0] == WRITE_TEXT_AND_CHECK_EXTRA_MESSAGE or next_action[0] == CHECK_EXTRA_MESSAGE:
            #                 if next_action[0] == WRITE_TEXT_AND_CHECK_EXTRA_MESSAGE:
            #                     link_lists = choose_and_write_to_file(next_action[2], active_OS_if_states, last_directory, last_title, [root_dir_generic, root_dir_os_specific_linux, root_dir_os_specific_windows, root_dir_os_specific_macos], link_lists, in_code_block)
            #                 next_action = check_if_statements(next_action[1], active_OS_if_states)
            #
            #             if next_action[0] == WRITE_TEXT:
            #                 link_lists = choose_and_write_to_file(next_action[2], active_OS_if_states, last_directory, last_title, [root_dir_generic, root_dir_os_specific_linux, root_dir_os_specific_windows, root_dir_os_specific_macos], link_lists, in_code_block)
            #
            # # write end of file for the last file
            # for i, OS in enumerate(["", "Linux", "Windows", "macOS"]):
            #     write_end_of_file(os.path.join(root_dirs[i], last_directory, last_title + ".json"), OS, link_lists[i], is_linux_tutorial, main_title, last_title)

    # remove_directory_tree(COPIES)
    # remove_directory_tree(IF_MANGLED_FILES)


################### run the script ###################
print("WARNING: This script generates a file structure that contains rather long filepaths. Depending on where the script is ran, some of these paths might exceed the maximum length allowed by the system resulting in problems opening the files.")
main()
print("Parsing finished successfully")
