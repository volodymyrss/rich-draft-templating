from __future__ import print_function


import os
import re
import jinja2
import numpy as np

def get_latex_jinja_env():
    return jinja2.Environment(
            block_start_string = '\BLOCK{',
            block_end_string = '}',
            variable_start_string = '\VAR{',
            variable_end_string = '}',
            comment_start_string = '\#{',
            comment_end_string = '}',
            line_statement_prefix = '%%\LINE',
            line_comment_prefix = '%#',
            trim_blocks = True,
            autoescape = False,
            loader = jinja2.FileSystemLoader(os.path.abspath('.')),
        undefined=jinja2.StrictUndefined,
    )

def extract_referenced_keys(draft_filename):
    reduced=[]
    for k in re.findall("\\VAR{(.*?)}", open(draft_filename).read()):
        if not k in reduced:
            print("found",k)
            reduced.append(k)
    return reduced

def render_definitions(latex_jinja_env,keys,data,output_filename=None):
    header = """
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%% generated by template.py, please do not edit directly
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% boilerplate

\def\\addVAR#1#2{\expandafter\gdef\csname my@data@\detokenize{#1}\endcsname{#2}}
\def\VAR#1{%
  \ifcsname my@data@\detokenize{#1}\endcsname
    \csname my@data@\detokenize{#1}\expandafter\endcsname
  \else
    \expandafter\ERROR
  \\fi
}

% extracted definitions

"""

    output=header
    for key in keys:
        rtemplate = latex_jinja_env.from_string("\VAR{"+key+"}")

        try:
            value=np.unicode(rtemplate.render(data)).encode('utf8')
        except Exception as e:
            print("unable to render",key,e)

            value="XXX"

        output+="\\addVAR{"+key+"}{"+value+"}\n"

    if output_filename is not None:
        with open(output_filename, "w") as output_file:
            output_file.write(output)
    else:
        return output


def render_draft(latex_jinja_env,data,input_filename=None,input_template_string=None,output_filename=None,write_header=True):

    if input_template_string is not None:
        template = latex_jinja_env.from_string(input_template_string)
    else:
        template = latex_jinja_env.get_template(input_filename)

    if write_header:
        header = """
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%% generated by template.py, please do not edit directly
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
"""
    else:
        header=""

    rendering=np.unicode(header+template.render(**data)).encode('utf8')

    if output_filename is not None:
        open(output_filename,"w").write(rendering)
    else:
        return rendering