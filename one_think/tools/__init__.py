from typing import Tuple


class Tool:
    description = ""
    name = ""
    arguments ={

    }
    def __init__(self):
        pass

    def execute(self, arguments: dict[str, str] = None)-> Tuple[str, str]:
        pass

    def get_full_information(self):
        pass

    def __str__(self):
        return f'''Tool: {self.name} - {self.description} | Arguments: {self.arguments}'''


