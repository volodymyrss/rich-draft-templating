from __future__ import print_function


import os
import re
import jinja2
import yaml
import numpy as np
from jinja2.utils import concat

import logging

logger = logging.getLogger('ddpaper.render')

from ddpaper.filters import setup_custom_filters

# FROM: https://github.com/duelafn/python-jinja2-apci/blob/master/jinja2_apci/error.py
from jinja2 import nodes
from jinja2.ext import Extension
from jinja2.exceptions import TemplateRuntimeError

import importlib

class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)

    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise KeyError('key {} is not available, have keys: {}'.format(k, ", ".join(self.keys())))

class RaiseExtension(Extension):
    # This is our keyword(s):
    tags = set(['raise'])

    # See also: jinja2.parser.parse_include()
    def parse(self, parser):
        # the first token is the token that started the tag. In our case we
        # only listen to "raise" so this will be a name token with
        # "raise" as value. We get the line number so that we can give
        # that line number to the nodes we insert.
        lineno = next(parser.stream).lineno

        # Extract the message from the template
        message_node = parser.parse_expression()

        return nodes.CallBlock(
            self.call_method('_raise', [message_node], lineno=lineno),
            [], [], [], lineno=lineno
        )

    def _raise(self, msg, caller):
        raise TemplateRuntimeError(msg)

def get_latex_jinja_env():
    env=jinja2.Environment(
            block_start_string = r'\BLOCK{',
            block_end_string = '}',
            variable_start_string = r'\VAR{',
            variable_end_string = '}',
            comment_start_string = r'\#{',
            comment_end_string = '}',
            line_statement_prefix = r'%%\LINE',
            line_comment_prefix = '%#',
            trim_blocks = True,
            autoescape = False,
            loader = jinja2.FileSystemLoader(os.path.abspath('.')),
        undefined=jinja2.StrictUndefined,
        extensions=[RaiseExtension],
    )
    setup_custom_filters(env)
    return  env

def extract_referenced_keys(template_string):
    reduced=[]
    for k in re.findall(r"\\VAR{(.*?)}", template_string):
        if not k in reduced:
            print("found",k)
            reduced.append(k)
    return reduced

def extract_template_data(template_string):
    keys = extract_referenced_keys(template_string)

    re_eq = re.compile("(.*?)==(.*)")

    template_data = []

    for key in keys:
        r = re_eq.match(key)
        if r:
            k,v = r.groups()
        else:
            k = key
            v = None

        template_data.append((key, k, v))

    return template_data

def load_modules_in_env(latex_jinja_env, key):
    if key.strip().startswith('local.'):
        local_marker, module_name, remainder = key.split(".",2)

        module = importlib.import_module(module_name)

        logger.info('imported %s as %s',module_name,module)

        latex_jinja_env.globals['local'] = AttrDict(**{module_name: module})

        return key #module_name+"."+remainder

    if key.strip().startswith('oda.'):
        logger.info("loading oda plugin")

        module = importlib.import_module("odahub")

        logger.info('imported odahub as %s', module)

        latex_jinja_env.globals['oda'] = AttrDict(**{'evaluate': module.evaluate})

    return key


def compute_value(latex_jinja_env, key, data):
    newkey = load_modules_in_env(latex_jinja_env, key)

    logger.info('compute value for key %s', newkey)

    rtemplate = latex_jinja_env.from_string("\VAR{"+newkey+"}")

    try:
        d_value=np.unicode(rtemplate.render(data)) #.encode('utf8')
    except Exception as e:
        print("unable to render",key,e)

        d_value="XXX"

    return d_value


def render_definitions(latex_jinja_env,template_string,data):
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
\def\DATA#1{%
  \ifcsname my@data@\detokenize{#1}\endcsname
    \csname my@data@\detokenize{#1}\expandafter\endcsname
  \else
    \expandafter\ERROR
  \\fi
}

\def\PREPROC#1{%
}

% extracted definitions

"""

    template_string, preprocs = preproc_template(template_string)

    preprocs_dict = dict(preprocs)

    logger.info("preprocs dict", preprocs_dict)

    template_data = extract_template_data(template_string)

    output=header
    for l_key, key, value in template_data:
        d_value = compute_value(latex_jinja_env, key, data)

        logger.debug("key: %s, value: %s; long key: %s; data value %s"%(key, value, l_key, d_value))

        nref = 0
        for k,v in preprocs_dict.items():
            if l_key == v:
                output+=r"\addVAR{"+k+"}{"+d_value+"}\n"
                nref += 1

        if nref == 0:
            output+=r"\addVAR{"+l_key+"}{"+d_value+"}\n"
    

    return output

def preproc_template(template_string):
    logger.info("preprocessing template %s", template_string)

    re_preproc_sources = re.compile(r"\\PREPROC{(.*?)}", re.M)

    preprocs = []

    for preproc_source_fn in re_preproc_sources.findall(template_string):
        for re_in, re_out in yaml.load(open(preproc_source_fn)).items():
            logger.info('applying preproc %s => %s', re_in, re_out)

            for g in re.findall("("+re_in+")", template_string):
                f_re_in = g[0]
                logger.info("found preproc target %s", f_re_in)

                f_re_out = re.sub(re_in, re_out, f_re_in)

                preprocs.append((f_re_in, f_re_out))

            template_string = re.sub(re_in, re_out, template_string)

    template_string = re_preproc_sources.sub("", template_string)

    logger.info("preproc yeilds %s", template_string)

    return template_string, preprocs

def render_draft(latex_jinja_env, template_string, data, write_header=True):
    re_var = re.compile(r"\\VAR{(.*?)==(.*?)}")

    draft_vars = re_var.findall(template_string)
    for k, v in draft_vars:
        logger.info("draft var: %s %s",k,v)
    
    template_string, preprocs = preproc_template(template_string)

    ready_template = re_var.sub(r"\\VAR{\1}", template_string)
    
    re_all_var = re.compile(r"\\VAR{(.*?)}")
    draft_vars = re_all_var.findall(template_string)

    for k in draft_vars:
        load_modules_in_env(latex_jinja_env, k)
        logger.info("processed draft var: %s",k)

    logger.debug("processed template:\n %s",ready_template)

    template = latex_jinja_env.from_string(ready_template)

    if write_header:
        header = """
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%% generated by template.py, please do not edit directly
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
"""
    else:
        header=""

    raw_render=concat(
        template.root_render_func(template.new_context(data,shared=False))
    )

    rendering=np.unicode(header+raw_render) 

    return rendering

def render_update(latex_jinja_env,template_string,data):
    template_data = extract_template_data(template_string)

    updated_template = template_string

    for l_key, key, value in template_data:
        d_value = compute_value(latex_jinja_env, key, data)
        
        logger.debug("key: %s, value: %s; long key: %s; data value %s"%(key, value, l_key, d_value))

        updated_template = updated_template.replace(
                r"\VAR{%s==%s}"%(key,value),
                r"\VAR{%s == %s}"%(key.strip(),d_value.strip()),
            )

    return updated_template

def render_validate(latex_jinja_env,template_string,data):
    template_data = extract_template_data(template_string)

    for l_key, key, value in template_data:
        d_value = compute_value(latex_jinja_env, key, data)
        logger.info("key: %s value: \"%s\", new value: \"%s\""%(key, value, d_value))

        if value is not None and value != d_value:
            raise RuntimeError("invalid! key: %s value %s: new value: %s"%(key, value, d_value))

    return ""
