import colorama

from scientistgtp.code_runner import CodeRunner
from scientistgtp.exceptions import FailedExtractingCode, FailedRunningCode, FailedLoadingOutput
from scientistgtp.env import SUPPORTED_PACKAGES
from scientistgtp.utils import format_str

from .converser_gpt import ConverserGPT


MAX_DEBUGGING_ATTEMPTS = 3
MAX_ITERATIONS_PER_ATTEMPT = 5


class DebuggerGPT(ConverserGPT):
    """
    Starting with a conversation which ends with a code-request from the user, DebuggerGPT interacts with chatgpt to
    get a functional code, which creates a desired output file.

    Interactions include:
    * missing packages
    * error messages
    * output file not created
    """

    def _run_code_from_last_response(self):
        return CodeRunner(response=self.conversation.get_last_response(),
                          output_file=self.OUTPUT_FILENAME,
                          ).run_code()

    def _specify_allowed_packages(self, error_message: str):
        prompt = format_str(f"""
            I ran the code and got the following error message:
             ```
             {error_message}
             ```
            Please rewrite the code using only {', '.join(SUPPORTED_PACKAGES)}. 
            """)
        self.conversation.append_user_message(prompt)

    def _specify_error_message(self, error_message: str):
        prompt = format_str(f"""
            I ran the code and got the following error message:
             ```
             {error_message}
             ```
            Please rewrite the complete code again with this error corrected. 
            """)
        self.conversation.append_user_message(prompt)

    def _specify_missing_output(self):
        prompt = format_str(f"""
            I ran the code, but it didn't generate the desired output file ({self.OUTPUT_FILENAME}).
            Please rewrite the complete code again with this error corrected. 
            """)
        self.conversation.append_user_message(prompt)

    def debug_and_run_code(self):
        """
        Interact with chatgpt until getting a functional code that can run locally and produce desired output file.
        :return: content of the file produced by the gpt code.
        """

        self.save_current_state_by_name('initial')

        for debug_attempt in range(MAX_DEBUGGING_ATTEMPTS):
            self.reset_state_to('initial')
            if debug_attempt > 0:
                print(colorama.Fore.RED +
                      f'Debugging failed. Retrying from scratch({debug_attempt}/{MAX_DEBUGGING_ATTEMPTS}).' +
                      colorama.Style.RESET_ALL)
            for iteration_num in range(MAX_ITERATIONS_PER_ATTEMPT):
                self.conversation.get_response_from_chatgpt()
                try:
                    result = self._run_code_from_last_response()
                except FailedExtractingCode as e:
                    # no code, or multiple code snippets, were found.
                    # remove the last gpt response to re-generate:
                    self.conversation.pop(-1)
                    print(colorama.Fore.RED +
                          'Failed extracting code from gpt response. Regenerating response...' +
                          colorama.Style.RESET_ALL)
                except FailedRunningCode as e:
                    if isinstance(e.exception, ImportError):
                        # chatgpt tried using a package we do not support
                        self._specify_allowed_packages(str(e.exception))
                    else:
                        # the code failed on other errors.
                        # indicate error message to chatgpt.
                        self._specify_error_message(str(e.exception))
                except FailedLoadingOutput:
                    # Code ran, but the output file was not created.
                    self._specify_missing_output()
                except Exception:
                    raise
                else:
                    # The code ran just fine.
                    return result
