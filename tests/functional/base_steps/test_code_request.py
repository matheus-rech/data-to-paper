from dataclasses import dataclass, field
from typing import Iterable

from _pytest.fixtures import fixture

from scientistgpt.base_steps import DataframeChangingCodeProductsGPT
from scientistgpt.conversation.actions_and_conversations import ActionsAndConversations
from scientistgpt.projects.scientific_research.scientific_products import ScientificProducts
from scientistgpt.run_gpt_code.types import CodeAndOutput
from scientistgpt.servers.chatgpt import OPENAI_SERVER_CALLER
from scientistgpt.utils.file_utils import run_in_directory
from tests.functional.base_steps.utils import TestAgent


@fixture()
def code_running_converser(tmpdir_with_csv_file):
    @dataclass
    class TestDataframeChangingCodeProductsGPT(DataframeChangingCodeProductsGPT):
        conversation_name: str = 'test'
        user_agent: TestAgent = TestAgent.PERFORMER
        assistant_agent: TestAgent = TestAgent.REVIEWER
        actions_and_conversations: ActionsAndConversations = field(default_factory=ActionsAndConversations)
        allowed_created_files: Iterable[str] = ('*.csv',)
        output_filename: str = None
        code_name: str = 'Testing'

        @property
        def data_folder(self):
            return tmpdir_with_csv_file

        @property
        def data_filenames(self):
            return ['test.csv']

    return TestDataframeChangingCodeProductsGPT()


code_reading_csv = r"""import pandas as pd
df1 = pd.read_csv('test.csv')
df1['new_column'] = df1['a'] + df1['b']
df1.to_csv('test_modified.csv')
"""

code_reading_csv_keywords_in_description = ('test_modified.csv', 'test.csv', 'new_column')

code_creating_csv = r"""import pandas as pd
df2 = pd.DataFrame([["n", "e", "w"], ["r", "o", "w"]], columns=['a', 'b', 'c'])
df2.to_csv('new_df.csv')
"""

code_reading_and_creating_csv = code_reading_csv + code_creating_csv

code_reading_not_changing_existing_series = r"""import pandas as pd
import copy
df1 = pd.read_csv('test.csv')
df2 = copy.copy(df1)
assert df2.is_overridden()
df2['new_column'] = df2['a'] + df2['b']
"""

code_reading_and_creating_csv_not_changing_existing_series = \
    code_reading_not_changing_existing_series + code_creating_csv

new_column_dict_explanation = """
the column explanation is:
{
    'new_column': 'this is just a new column',
}
"""


def test_request_code_with_adding_new_column(code_running_converser):
    with OPENAI_SERVER_CALLER.mock(
            [f'Python value:\n```python\n{code_reading_csv}\n```\nShould be all good.',
             new_column_dict_explanation],
            record_more_if_needed=False):
        code_and_outputs = {"data_preprocessing": code_running_converser.get_analysis_code()}
        scientific_products = ScientificProducts()
        scientific_products.codes_and_outputs = code_and_outputs
        for keyword in code_reading_csv_keywords_in_description:
            assert keyword in scientific_products['created_files_description:data_preprocessing'].description
