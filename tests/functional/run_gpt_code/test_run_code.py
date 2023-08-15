import os
import time

import pytest
from _pytest.fixtures import fixture

from data_to_paper.run_gpt_code.dynamic_code import RunCode, CODE_MODULE, FailedRunningCode
from data_to_paper.run_gpt_code.exceptions import CodeUsesForbiddenFunctions, \
    CodeWriteForbiddenFile, CodeImportForbiddenModule, UnAllowedFilesCreated
from data_to_paper.utils import dedent_triple_quote_str


def test_run_code_on_legit_code():
    code = dedent_triple_quote_str("""
        def f():
            return 'hello'
        """)
    RunCode().run(code)
    assert CODE_MODULE.f() == 'hello'


def test_run_code_correctly_reports_exception():
    code = dedent_triple_quote_str("""
        # line 1
        # line 2
        raise Exception('error')
        # line 4
        """)
    try:
        RunCode().run(code)
    except FailedRunningCode as e:
        assert e.exception.args[0] == 'error'
        lineno, line, msg = e.get_lineno_line_message()
        assert lineno == 3
        assert line == "raise Exception('error')"
    else:
        assert False, 'Expected to fail'


def test_run_code_catches_warning():
    code = dedent_triple_quote_str("""
        import warnings
        warnings.warn('be careful', UserWarning)
        """)
    with pytest.raises(FailedRunningCode) as e:
        RunCode(warnings_to_raise=[UserWarning]).run(code)
    error = e.value
    lineno, line, msg = error.get_lineno_line_message()
    assert msg == 'be careful'
    assert lineno == 2


def test_run_code_timeout():
    code = dedent_triple_quote_str("""
        import time
        # line 2
        time.sleep(2)
        # line 4
        """)
    try:
        RunCode(timeout_sec=1).run(code)
    except FailedRunningCode as e:
        assert isinstance(e.exception, TimeoutError)
        lineno, line, msg = e.get_lineno_line_message()
        assert lineno == 3
        assert line == "time.sleep(2)"
    else:
        assert False, 'Expected to fail'


@pytest.mark.parametrize("forbidden_call", ['input', 'exit', 'quit', 'eval'])
def test_run_code_forbidden_functions(forbidden_call):
    time.sleep(0.1)
    code = dedent_triple_quote_str("""
        a = 1
        {}()
        """).format(forbidden_call)
    with pytest.raises(FailedRunningCode) as e:
        RunCode().run(code)
    error = e.value
    assert isinstance(error.exception, CodeUsesForbiddenFunctions)
    lineno, line, msg = error.get_lineno_line_message()
    assert lineno == 2
    assert line == '{}()'.format(forbidden_call)
    # TODO: some wierd bug - the message is not always the same:
    # assert forbidden_call in msg


def test_run_code_forbidden_function_print():
    code = dedent_triple_quote_str("""
        a = 1
        print(a)
        a = 2
        """)
    contexts = RunCode().run(code)
    issue_collector = contexts['IssueCollector']
    assert 'print' in issue_collector.issues[0].issue


@pytest.mark.parametrize("forbidden_import,module_name", [
    ('import os', 'os'),
    ('from os import path', 'os'),
    ('import os.path', 'os.path'),
    ('import sys', 'sys'),
    ('import matplotlib', 'matplotlib'),
    ('import matplotlib as mpl', 'matplotlib'),
    ('import matplotlib.pyplot as plt', 'matplotlib.pyplot'),
])
def test_run_code_forbidden_import(forbidden_import, module_name):
    code = dedent_triple_quote_str("""
        import scipy
        import numpy as np
        {}
        """).format(forbidden_import)
    try:
        RunCode().run(code)
    except FailedRunningCode as e:
        assert isinstance(e.exception, CodeImportForbiddenModule)
        assert e.exception.module == module_name
        lineno, line, msg = e.get_lineno_line_message()
        assert lineno == 3
        assert line == forbidden_import
    else:
        assert False, 'Expected to fail'


def test_run_code_forbidden_import_should_not_raise_on_allowed_packages():
    code = dedent_triple_quote_str("""
        import pandas as pd
        import numpy as np
        from scipy.stats import chi2_contingency
        """)
    try:
        RunCode().run(code)
    except Exception as e:
        assert False, 'Should not raise, got {}'.format(e)
    else:
        assert True


def test_run_code_wrong_import():
    code = dedent_triple_quote_str("""
        from xxx import yyy
        """)
    try:
        RunCode().run(code)
    except FailedRunningCode as e:
        assert e.exception.fromlist == ('yyy', )


code = dedent_triple_quote_str("""
    with open('test.txt', 'w') as f:
        f.write('hello')
    """)


def test_run_code_raises_on_unallowed_open_files(tmpdir):
    with pytest.raises(FailedRunningCode) as e:
        RunCode(allowed_open_write_files=[], run_in_folder=tmpdir).run(code)
    error = e.value
    assert isinstance(error.exception, CodeWriteForbiddenFile)
    lineno, line, msg = error.get_lineno_line_message()
    assert lineno == 1
    assert line == "with open('test.txt', 'w') as f:"


def test_run_code_raises_on_unallowed_created_files(tmpdir):
    with pytest.raises(FailedRunningCode) as e:
        RunCode(allowed_open_write_files=None, allowed_create_files=(), run_in_folder=tmpdir).run(code)
    error = e.value
    assert isinstance(error.exception, UnAllowedFilesCreated)
    lineno, line, msg = error.get_lineno_line_message()
    assert lineno is None


def test_run_code_allows_allowed_files(tmpdir):
    os.chdir(tmpdir)
    RunCode(allowed_open_write_files=['test.txt']).run(code)
