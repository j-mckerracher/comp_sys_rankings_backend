import json


class UniversityFinder:
    def __init__(self, json_file_path):
        self.file_path = json_file_path
        with open(self.file_path, 'r') as file:
            universities = json.load(file)
            self.data = set()
            for university in universities:
                self.data.add(university['name'])
                if university['alias'] != "NOT AVAILABLE":
                    aliases = university['alias'].split("|")
                    for alias in aliases:
                        self.data.add(alias.strip())

    def search_university(self, university_name: str) -> bool:
        university_name = university_name.upper()
        for name in self.data:
            if university_name in name:
                return True
        return False


# source: https://public.opendatasoft.com/explore/dataset/us-colleges-and-universities/export/?flg=en-us
finder = UniversityFinder(r"C:\Users\jmckerra\PycharmProjects\comp_sys_rankings_backend\files\us-colleges-and-universities.json")