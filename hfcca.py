#!/usr/bin/env python
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
#  author: terry.yinzhe@gmail.com
#

"""
source_analyzer is a simple code complexity source_file_counter without caring about the C/C++ header files.
It can deal with C/C++/Objective C & TNSDL code. It count the NLOC (lines of code without comments), CCN 
(cyclomatic complexity number) and token count of _functions.
It requires python2.6 or above (early versions are not verified).
"""

VERSION="1.6.5"

import itertools

DEFAULT_CCN_THRESHOLD = 15

class FunctionInfo:
    def __init__(self, name, start_line):
        self.cyclomatic_complexity = 1
        self.NLOC = 1
        self.token_count = 0
        self.name = name
        self.function_name_with_param = name
        self.return_type = ""
        self.start_line = start_line
        self.parameter_count = 0
    def __eq__(self, other): return other == self.name
    def add_to_function_name(self, app):
        self.name += app
        self.function_name_with_param += app
    def long_name(self):
        return self.return_type + self.function_name_with_param
    def add_to_long_name(self, app):
        self.function_name_with_param += app
    def add_condition(self): self.cyclomatic_complexity += 1
    def add_token(self): self.token_count += 1
    def add_non_comment_line(self): self.NLOC += 1
    def add_parameter(self, token):
        if self.parameter_count == 0:
            self.parameter_count = 1
        if token == ",":
            self.parameter_count += 1

class FunctionsStatisticsListOfSourceFile(list):
    """
        UniversalCode is the code that is unrelated to any programming languages. The code could be:
        START_NEW_FUNCTION
            ADD_TO_FUNCTION_NAME
            ADD_TO_LONG_FUNCTION_NAME
                PARAMETER
            CONDITION
            TOKEN
        END_OF_FUNCTION
        
        A TokenTranslator will generate UniversalCode.
    """
    def __init__(self, parsed_code, filename):
        self.NLOC = 0
        self.current_function = None
        self.filename = filename
        self.functionInfos = []
        for fun in self._functions(parsed_code):
            self.append(fun)
        self._summarize()
        
    def START_NEW_FUNCTION(self, name_and_line):
        self.current_function = FunctionInfo(*name_and_line)
    
    def CONDITION(self, token): 
        self.TOKEN(token)
        self.current_function.add_condition()
    
    def TOKEN(self, text):
        self.current_function.add_token()
    
    def NEW_LINE(self, token): 
        self.NLOC += 1
        if self.current_function is not None:
            self.current_function.add_non_comment_line()
    
    def ADD_TO_LONG_FUNCTION_NAME(self, app):
        self.current_function.add_to_long_name(app)
    
    def ADD_TO_FUNCTION_NAME(self, app):
        self.current_function.add_to_function_name(app)
    
    def PARAMETER(self, token):
        self.current_function.add_parameter(token)
        self.ADD_TO_LONG_FUNCTION_NAME(" " + token)
        
    END_OF_FUNCTION = 1
    
    def _functions(self, parsed_code):
        for code, text in parsed_code:
            if code == FunctionsStatisticsListOfSourceFile.END_OF_FUNCTION:
                yield self.current_function
            else:
                code(self, text)
    
    def _summarize(self):
        self.average_NLOC = 0
        self.average_CCN = 0
        self.average_token = 0
        
        self.LOC = sum(fun.NLOC for fun in self)
        nloc = 0
        ccn = 0
        token = 0
        for fun in self:
            nloc += fun.NLOC
            ccn += fun.cyclomatic_complexity
            token += fun.token_count
        fc = len(self)
        if fc > 0:
            self.average_NLOC = nloc / fc
            self.average_CCN = ccn / fc
            self.average_token = token / fc
    
        self.NLOC = nloc
        self.CCN = ccn
        self.token = token

class TokenTranslatorBase:
    
    def __init__(self):
        self._state = self._GLOBAL
        self._current_line = 0
    
    def get_current_line(self):
        return self._current_line
    
    def getFunctions(self, tokens):
        for token, self._current_line in tokens:
            fun = self._read_token(token)
            if fun: yield fun
    
    def _read_token(self, token):
        if token.isspace():
            return FunctionsStatisticsListOfSourceFile.NEW_LINE, None
        else:
            return self._state(token)
    def remove_hash_if(self):
        self.conditions.remove("#if")

    
class CTokenTranslator(TokenTranslatorBase):
    
    def __init__(self):
        TokenTranslatorBase.__init__(self)
        self.conditions = set(['if', 'for', 'while', '&&', '||', 'case', '?', '#if', 'catch'])
        self.bracket_level = 0
        self.br_count = 0
    
    def _is_condition(self, token):
        return token in self.conditions
    
    def _GLOBAL(self, token):
        if token == '(':
            self.bracket_level += 1
            self._state = self._DEC
            return FunctionsStatisticsListOfSourceFile.ADD_TO_LONG_FUNCTION_NAME, token
        elif token == '::':
            self._state = self._NAMESPACE
        else:
            if token == 'operator':
                self._state = self._OPERATOR
            return FunctionsStatisticsListOfSourceFile.START_NEW_FUNCTION, (token, self._current_line)

    
    def _OPERATOR(self, token):
            if token != '(':
                self._state = self._GLOBAL
            return FunctionsStatisticsListOfSourceFile.ADD_TO_FUNCTION_NAME, ' ' + token
    
    def _NAMESPACE(self, token):
            self._state = self._OPERATOR if token == 'operator'  else self._GLOBAL
            return FunctionsStatisticsListOfSourceFile.ADD_TO_FUNCTION_NAME, "::" + token
    
    def _DEC(self, token):
        if token in ('(', "<"):
            self.bracket_level += 1
        elif token in (')', ">"):
            self.bracket_level -= 1
            if (self.bracket_level == 0):
                self._state = self._DEC_TO_IMP
        elif self.bracket_level == 1:
            return FunctionsStatisticsListOfSourceFile.PARAMETER, token
        return FunctionsStatisticsListOfSourceFile.ADD_TO_LONG_FUNCTION_NAME, " " + token
    
    def _DEC_TO_IMP(self, token):
        if token == 'const':
            return FunctionsStatisticsListOfSourceFile.ADD_TO_LONG_FUNCTION_NAME, " " + token
        elif token == '{':
            self.br_count += 1
            self._state = self._IMP
        else:
            self._state = self._GLOBAL
    
    def _IMP(self, token):
        if token == '{':
            self.br_count += 1
        elif token == '}':
            self.br_count -= 1
            if self.br_count == 0:
                self._state = self._GLOBAL
                return FunctionsStatisticsListOfSourceFile.END_OF_FUNCTION, ""      
        else:
            if self._is_condition(token):
                return FunctionsStatisticsListOfSourceFile.CONDITION, token
            if token not in '();':
                return FunctionsStatisticsListOfSourceFile.TOKEN, token
        
class ObjCTokenTranslator(CTokenTranslator):
    def __init__(self):
        CTokenTranslator.__init__(self)
        
    def _DEC_TO_IMP(self, token):
        if token in ("+", "-"):
            self._state = self._GLOBAL
        else:
            CTokenTranslator._DEC_TO_IMP(self, token)
            if self._state == self._GLOBAL:
                self._state = self._OBJC_DEC_BEGIN
                return FunctionsStatisticsListOfSourceFile.START_NEW_FUNCTION, (token, self._current_line)
    def _OBJC_DEC_BEGIN(self, token):
        if token == ':':
            self._state = self._OBJC_DEC
            return FunctionsStatisticsListOfSourceFile.ADD_TO_FUNCTION_NAME, token
        elif token == '{':
            self.br_count += 1
            self._state = self._IMP
        else:
            self._state = self._GLOBAL
    def _OBJC_DEC(self, token):
        if token == '(':
            self._state = self._OBJC_PARAM_TYPE
            return FunctionsStatisticsListOfSourceFile.ADD_TO_LONG_FUNCTION_NAME, token
        elif token == ',':
            pass
        elif token == '{':
            self.br_count += 1
            self._state = self._IMP
        else:
            self._state = self._OBJC_DEC_BEGIN
            return FunctionsStatisticsListOfSourceFile.ADD_TO_FUNCTION_NAME, " " + token
        
    def _OBJC_PARAM_TYPE(self, token):
        if token == ')':
            self._state = self._OBJC_PARAM
        return FunctionsStatisticsListOfSourceFile.ADD_TO_LONG_FUNCTION_NAME, " " + token
    def _OBJC_PARAM(self, token):
        self._state = self._OBJC_DEC

class SDLTokenTranslator(TokenTranslatorBase):
    def __init__(self):
        TokenTranslatorBase.__init__(self)
        self.last_token = ""
        self.prefix = ""
        self.statename = ""
        self.start_of_statement = True
        self.saved_process = ""
    def _GLOBAL(self, token):
            if token == 'PROCEDURE':
                self._state = self._DEC
            elif token == 'PROCESS':
                self._state = self._PROCESS
            elif token == 'STATE': 
                self._state = self._STATE
            elif token == 'START': 
                self.prefix = self.saved_process
                self._state = self._IMP
                return FunctionsStatisticsListOfSourceFile.START_NEW_FUNCTION, (self.prefix, self._current_line)
    def _DEC(self, token):
            self.prefix = "PROCEDURE " + token
            self._state = self._IMP
            return FunctionsStatisticsListOfSourceFile.START_NEW_FUNCTION, (self.prefix, self._current_line)
    def _PROCESS(self, token):
        self.prefix = "PROCESS " + token
        self.saved_process = self.prefix
        self._state = self._IMP
        return FunctionsStatisticsListOfSourceFile.START_NEW_FUNCTION, (self.prefix, self._current_line)
    def _STATE(self, token):
        self.statename = token
        self._state = self._BETWEEN_STATE_AND_INPUT
    def _BETWEEN_STATE_AND_INPUT(self, token):
        if token == 'INPUT':
            self._state = self._INPUT
    def _INPUT(self, token):
        if token != 'INTERNAL':
            self._state = self._IMP
            return FunctionsStatisticsListOfSourceFile.START_NEW_FUNCTION, (self.prefix + " STATE " + self.statename + " INPUT " + token, self._current_line)
    def _IMP(self, token):
        if token == 'PROCEDURE':
            self._state = self._DEC
            return False
        if token == 'ENDPROCEDURE' or token == 'ENDPROCESS' or token == 'ENDSTATE':
            self._state = self._GLOBAL
            return FunctionsStatisticsListOfSourceFile.END_OF_FUNCTION, ""
        if self.start_of_statement:     
            if token == 'STATE': 
                self._state = self._STATE
                return FunctionsStatisticsListOfSourceFile.END_OF_FUNCTION, ""     
            elif token == 'INPUT': 
                self._state = self._INPUT
                return FunctionsStatisticsListOfSourceFile.END_OF_FUNCTION, ""     
        condition = self._is_condition(token, self.last_token)

        self.last_token = token
        if not token.startswith("#"):
            self.start_of_statement = (token == ';')
        if condition:
            return FunctionsStatisticsListOfSourceFile.CONDITION, token
        return FunctionsStatisticsListOfSourceFile.TOKEN, token
        
    conditions = set(['WHILE', 'AND', 'OR', '#if'])
    def _is_condition(self, token, last_token):
        if token == ':' and last_token == ')':
            return FunctionsStatisticsListOfSourceFile.END_OF_FUNCTION, ""
        return token in self.conditions

import re

c_pattern = re.compile(r".*\.(c|C|cpp|CPP|CC|cc|mm)$")
sdl_pattern = re.compile(r".*\.(sdl|SDL)$")
objc_pattern = re.compile(r".*\.(m)$")

hfcca_language_infos = {
                 'c/c++': {
                  'name_pattern': c_pattern,
                  'creator':CTokenTranslator},
                    
                 'sdl' : {
                  'name_pattern': sdl_pattern,
                  'creator':SDLTokenTranslator},
                  
                  'objC' : {
                  'name_pattern': objc_pattern,
                  'creator':ObjCTokenTranslator}
            }

def get_parser_by_file_name(filename):
        for lan in hfcca_language_infos:
            info = hfcca_language_infos[lan]
            if info['name_pattern'].match(filename):
                return info['creator']
            
def get_parser_by_file_name_otherwise_default(filename):
    for lan in hfcca_language_infos:
        info = hfcca_language_infos[lan]
        if info['name_pattern'].match(filename):
            return info['creator']()
    return hfcca_language_infos['c/c++']['creator']()
            
class FileAnalyzer:
    ''' A FileAnalyzer works as a function. It takes filename as parameter.
        Returns a list of function infos in this file.
    '''
    
    open = open
    
    def __init__(self, noCountPre=False):
        self.noCountPre = noCountPre
        
    def __call__(self, filename):
        return self.analyze(filename)
    

    def analyze_source_code_with_parser1(self, filename, code, parser):
        tokens = generate_tokens(code)
        result = self.analyze_source_code_with_parser(filename, parser, tokens)
        return result

    def analyze(self, filename):
        code = self._readFileContent(filename)
        parser = get_parser_by_file_name_otherwise_default(filename)
        if self.noCountPre:
            parser.remove_hash_if()
        result = self.analyze_source_code_with_parser1(filename, code, parser)
        return result
       

    def analyze_source_code_with_parser(self, filename, parser, tokens):
        result = FunctionsStatisticsListOfSourceFile(parser.getFunctions(tokens), filename)
        return result

    def _readFileContent(self, filename):
        f = self.open(filename)
        code = f.read()
        f.close()
        return code

token_pattern = re.compile(r"(\w+|/\*|//|:=|::|>=|\*=|\*\*|\*|>|&=|&&|&|#\s*define|#\s*if|#\s*else|#\s*endif|#\s*\w+|[!%^&\*\-=+\|\\<>/\]\+]+|.)", re.M | re.S)

def generate_tokens(source_code):
    for t, l in generate_tokens_from_code(source_code):
        if not t.startswith('#define') and not t.startswith('/*') and not t.startswith('//') :
            yield t, l
            
def generate_tokens_from_code(source_code):
    in_middle_of_empty_lines = False
    for (token, line) in generate_tokens_from_code_with_multiple_newlines(source_code):
        if token != '\n' or not in_middle_of_empty_lines:
            yield token, line
        in_middle_of_empty_lines = (token == '\n')
            
def generate_tokens_from_code_with_multiple_newlines(source_code):
    index = 0
    line = 1
    while 1:
        m = token_pattern.match(source_code, index)
        if not m:
            break
        token = m.group(0)
        if token == '\n': line += 1
        
        if token.startswith("#"):
            token = "#" + token[1:].strip()
            
        if token == "#define":
            while(1):
                bindex = index + 1
                index = source_code.find('\n', bindex)  
                if index == -1:
                    break
                if not source_code[bindex:index].rstrip().endswith('\\'):
                    break
            if index == -1:
                break
            token = source_code[m.start(0):index]
        elif token == '/*':
            index = source_code.find("*/", index + 2)
            if index == -1:
                break
            index += 2
            token = source_code[m.start(0):index]
        elif token == '//' or token == '#if' or token == '#endif':
            index = source_code.find('\n', index)  
            if index == -1:
                break
        elif token == '"' or token == '\'':
            while(1):
                index += 1
                index = source_code.find(token, index)  
                if index == -1:
                    break
                if source_code[index - 1] == '\\' and source_code[index - 2] != '\\':
                    continue
                break
            if index == -1:
                break
            token = source_code[m.start(0):index + 1]
            index = index + 1
        else:
            index = m.end(0)
        line += (len(token.splitlines()) - 1)
        if not token.isspace() or token == '\n':
            yield token, line
                
import sys

def print_function_info_header():
    print("==============================================================")
    print("  NLOC    CCN  token  param    function@line@file")
    print("--------------------------------------------------------------")

def print_function_info(fun, filename, option):
    output_params = {
        'NLOC': fun.NLOC,
        'CCN': fun.cyclomatic_complexity,
        'token': fun.token_count,
        'param': fun.parameter_count,
        'name': fun.name,
        'line': fun.start_line,
        'file': filename
    }
    output_format = "%(NLOC)6d %(CCN)6d %(token)6d %(param)6d    %(name)s@%(line)s@%(file)s"
    if option.verbose:
        output_params['name'] = fun.long_name()
    if option.warnings_only:
        output_format = "%(file)s:%(line)s: warning: %(name)s has %(CCN)d CCN and %(param)d params (%(NLOC)d NLOC, %(token)d tokens)"
    print(output_format % output_params)

def print_warnings(option, saved_result):
    warning_count = 0
    if not option.warnings_only:
        print(("\n" +
              "======================================\n"+
              "!!!! Warnings (CCN > %d) !!!!\n"+
              "======================================") % option.CCN)
    for f in saved_result:
        for fun in f:
            if fun.cyclomatic_complexity > option.CCN or fun.parameter_count > option.arguments:
                warning_count += 1
                print_function_info(fun, f.filename, option)

    if warning_count == 0:
        print("No warning found. Excellent!")
            
    return warning_count

def print_total(warning_count, saved_result, option):
    all_fun = list(itertools.chain(*saved_result))
    cnt = len(all_fun)
    if (cnt == 0):
        cnt = 1
    tNLOC = sum([f.NLOC for f in all_fun])
    if (tNLOC == 0):
        tNLOC = 1
    total_info = (
                  tNLOC, tNLOC / cnt,
                  float(sum([f.cyclomatic_complexity for f in all_fun])) / cnt,
                  float(sum([f.token_count for f in all_fun])) / cnt,
                  cnt,
                  warning_count,
                  float(warning_count) / cnt,
                  float(sum([f.NLOC for f in all_fun if f.cyclomatic_complexity > option.CCN])) / tNLOC
                  )

    if not option.warnings_only:
        print("=================================================================================")
        print("Total NLOC  Avg.NLOC  Avg CCN  Avg token  Fun Cnt  Warning cnt   Fun Rt   NLOC Rt  ")
        print("--------------------------------------------------------------------------------")
        print("%10d%10d%9.2f%11.2f%9d%13d%10.2f%8.2f" % total_info)

def print_and_save_detail_information(allStatistics, option):
    saved_result = []
    if (option.warnings_only):
        saved_result = allStatistics
    else:
        print_function_info_header()
        for fileStatistics in allStatistics:
            saved_result.append(fileStatistics)
            for fun in fileStatistics:
                print_function_info(fun, fileStatistics.filename, option)
        
        print("--------------------------------------------------------------")
        print("%d file analyzed." % (len(saved_result)))
        print("==============================================================")
        print("LOC    Avg.NLOC AvgCCN Avg.ttoken  function_cnt    file")
        print("--------------------------------------------------------------")
        for fileStatistics in saved_result:
            print("%7d%7d%7d%10d%10d     %s" % (fileStatistics.LOC, fileStatistics.average_NLOC, fileStatistics.average_CCN, fileStatistics.average_token, len(fileStatistics), fileStatistics.filename))
    
    return saved_result

def print_result(r, option):
    saved_result = print_and_save_detail_information(r, option)
    warning_count = print_warnings(option, saved_result)
    print_total(warning_count, saved_result, option)
    if option.number > warning_count:
        sys.exit(1)

def xml_output(result, options):
    ''' Thanks for Holy Wen from Nokia Siemens Networks to let me use his code
        to put the result into xml file that is compatible with cppncss.
        Jenkens has plugin for cppncss format result to display the diagram.
    '''
    import xml.dom.minidom

    impl = xml.dom.minidom.getDOMImplementation()
    doc = impl.createDocument(None, "cppncss", None)
    root = doc.documentElement

    measure = doc.createElement("measure")
    measure.setAttribute("type", "Function")
    labels = doc.createElement("labels")
    label1 = doc.createElement("label")
    text1 = doc.createTextNode("Nr.")
    label1.appendChild(text1)
    label2 = doc.createElement("label")
    text2 = doc.createTextNode("NCSS")
    label2.appendChild(text2)
    label3 = doc.createElement("label")
    text3 = doc.createTextNode("CCN")
    label3.appendChild(text3)
    labels.appendChild(label1)
    labels.appendChild(label2)
    labels.appendChild(label3)
    measure.appendChild(labels)
    
    Nr = 0
    total_func_ncss = 0
    total_func_ccn = 0
    
    for source_file in result:
        file_name = source_file.filename
        for func in source_file:
            Nr += 1
            item = doc.createElement("item")
            item.setAttribute("name", "%s(...) at %s:0" % (func.name, file_name))
            value1 = doc.createElement("value")
            text1 = doc.createTextNode(str(Nr))
            value1.appendChild(text1)
            item.appendChild(value1)
            value2 = doc.createElement("value")
            text2 = doc.createTextNode(str(func.NLOC))
            value2.appendChild(text2)
            item.appendChild(value2)
            value3 = doc.createElement("value")
            text3 = doc.createTextNode(str(func.cyclomatic_complexity))
            value3.appendChild(text3)
            item.appendChild(value3)
            measure.appendChild(item)
            total_func_ncss += func.NLOC
            total_func_ccn += func.cyclomatic_complexity
        
        if Nr != 0:
            average_ncss = doc.createElement("average")
            average_ncss.setAttribute("lable", "NCSS")
            average_ncss.setAttribute("value", str(total_func_ncss / Nr))
            measure.appendChild(average_ncss)
            
            average_ccn = doc.createElement("average")
            average_ccn.setAttribute("lable", "CCN")
            average_ccn.setAttribute("value", str(total_func_ccn / Nr))
            measure.appendChild(average_ccn)
    
    root.appendChild(measure)

    measure = doc.createElement("measure")
    measure.setAttribute("type", "File")
    labels = doc.createElement("labels")
    label1 = doc.createElement("label")
    text1 = doc.createTextNode("Nr.")
    label1.appendChild(text1)
    label2 = doc.createElement("label")
    text2 = doc.createTextNode("NCSS")
    label2.appendChild(text2)
    label3 = doc.createElement("label")
    text3 = doc.createTextNode("CCN")
    label3.appendChild(text3)
    label4 = doc.createElement("label")
    text4 = doc.createTextNode("Functions")
    label4.appendChild(text4)
    labels.appendChild(label1)
    labels.appendChild(label2)
    labels.appendChild(label3)
    labels.appendChild(label4)
    measure.appendChild(labels)
    
    file_NR = 0
    file_total_ncss = 0
    file_total_ccn = 0
    file_total_funcs = 0
    
    for source_file in result:
        file_NR += 1
        item = doc.createElement("item")
        item.setAttribute("name", source_file.filename)
        value1 = doc.createElement("value")
        text1 = doc.createTextNode(str(file_NR))
        value1.appendChild(text1)
        item.appendChild(value1)
        value2 = doc.createElement("value")
        text2 = doc.createTextNode(str(source_file.NLOC))
        value2.appendChild(text2)
        item.appendChild(value2)
        value3 = doc.createElement("value")
        text3 = doc.createTextNode(str(source_file.CCN))
        value3.appendChild(text3)
        item.appendChild(value3)
        value4 = doc.createElement("value")
        text4 = doc.createTextNode(str(len(source_file)))
        value4.appendChild(text4)
        item.appendChild(value4)
        measure.appendChild(item)
        file_total_ncss += source_file.NLOC
        file_total_ccn += source_file.CCN
        file_total_funcs += len(source_file)
    
    if file_NR != 0:
            average_ncss = doc.createElement("average")
            average_ncss.setAttribute("lable", "NCSS")
            average_ncss.setAttribute("value", str(file_total_ncss / file_NR))
            measure.appendChild(average_ncss)
            
            average_ccn = doc.createElement("average")
            average_ccn.setAttribute("lable", "CCN")
            average_ccn.setAttribute("value", str(file_total_ccn / file_NR))
            measure.appendChild(average_ccn)
            
            average_funcs = doc.createElement("average")
            average_funcs.setAttribute("lable", "Functions")
            average_funcs.setAttribute("value", str(file_total_funcs / file_NR))
            measure.appendChild(average_funcs)
            
    sum_ncss = doc.createElement("sum")
    sum_ncss.setAttribute("lable", "NCSS")
    sum_ncss.setAttribute("value", str(file_total_ncss))
    measure.appendChild(sum_ncss)
    sum_ccn = doc.createElement("sum")
    sum_ccn.setAttribute("lable", "CCN")
    sum_ccn.setAttribute("value", str(file_total_ccn))
    measure.appendChild(sum_ccn)
    sum_funcs = doc.createElement("sum")
    sum_funcs.setAttribute("lable", "Functions")
    sum_funcs.setAttribute("value", str(file_total_funcs))
    measure.appendChild(sum_funcs)
            
    root.appendChild(measure)
    
    xmlString = doc.toprettyxml()
    return xmlString

def createHfccaCommandLineParser():
    from optparse import OptionParser
    parser = OptionParser(version=VERSION)
    parser.add_option("-v", "--verbose",
            help="Output in verbose mode (long function name)",
            action="store_true",
            dest="verbose",
            default=False)
    parser.add_option("-C", "--CCN",
            help="Threshold for cyclomatic complexity number warning. _functions with CCN bigger than this number will be shown in warning",
            action="store",
            type="int",
            dest="CCN",
            default=DEFAULT_CCN_THRESHOLD)
    parser.add_option("-w", "--warnings_only",
            help="Show warnings only, using clang/gcc's warning format for printing warnings. http://clang.llvm.org/docs/UsersManual.html#cmdoption-fdiagnostics-format",
            action="store_true",
            dest="warnings_only",
            default=False)
    parser.add_option("-i", "--ignore_warnings",
            help="If the number of warnings is equal or less than the number, the tool will exit normally, otherwize it will generate error. Useful in makefile when improving legacy code.",
            action="store",
            type="int",
            dest="number",
            default=0)
    parser.add_option("-x", "--exclude",
            help="Exclude files that match this pattern. * matches everything, ? matches any single characoter, \"./folder/*\" exclude everything in the folder, recursively. Multiple patterns can be specified. Don't forget to add \"\" around the pattern.",
            action="append",
            dest="exclude",
            default=[])
    parser.add_option("-X", "--xml",
            help="Generate XML in cppncss style instead of the normal tabular output. Useful to generate report in Hudson server",
            action="store_true",
            dest="xml",
            default=None)
    parser.add_option("-a", "--arguments",
            help="Limit for number of parameters",
            action="store",
            type="int",
            dest="arguments",
            default=100)
    parser.add_option("-P", "--no_preprocessor_count",
            help="By default, a #if will also increase the complexity. Adding this option to ignore them",
            action="store_true",
            dest="no_preprocessor_count",
            default=False)
    parser.add_option("-t", "--working_threads",
            help="number of working threads. The default value is 1.",
            action="store",
            type="int",
            dest="working_threads",
            default=1)
    
    parser.usage = "source_analyzer.py [options] [PATH or FILE] [PATH] ... "
    parser.description = __doc__
    return parser

def mapFilesToAnalyzer(files, fileAnalyzer, working_threads):
    try:
        # python 2.6 cannot work properly with multiple threading
        if sys.version_info[0:2] == (2,6): raise 
        import multiprocessing
        it = multiprocessing.Pool(processes=working_threads)
        mapFun = it.imap_unordered
    except:
        try:
            mapFun = itertools.imap
        except:
            mapFun = map
    r = mapFun(fileAnalyzer, files)
    return r

import os
import fnmatch

def _notExluded(str_to_match, patterns):
    return get_parser_by_file_name(str_to_match) and \
        all(not fnmatch.fnmatch(str_to_match, p) for p in patterns)

def getSourceFiles(SRC_DIRs, exclude_patterns):
    for SRC_DIR in SRC_DIRs:
        if os.path.isfile(SRC_DIR) and get_parser_by_file_name(SRC_DIR):
            yield SRC_DIR
        else:
            for root, _, files in os.walk(SRC_DIR, topdown=False):
                for filename in files:
                    full_path_name = os.path.join(root, filename)
                    if _notExluded(full_path_name, exclude_patterns):
                        yield full_path_name

def analyze(paths, options={}):
    ''' This is the most important function of hfcca.
        It analyze the given paths with the options.
        Can be used directly by other Python application.
    '''
    files = getSourceFiles(paths, options.exclude)
    fileAnalyzer = FileAnalyzer(options.no_preprocessor_count)
    r = mapFilesToAnalyzer(files, fileAnalyzer, options.working_threads)
    return r

def hfcca_main(argv):
    options, args = createHfccaCommandLineParser().parse_args(args = argv)
    paths = ["."] if len(args) == 1 else args[1:]
    r = analyze(paths, options)
    if options.xml:
        print (xml_output(list(r), options))
    else:
        print_result(r, options)

def main():
    hfcca_main(sys.argv)
        
if __name__ == "__main__":
    main()