class CategorizeVenue:
    def __init__(self):
        self.area_to_conference_map = {
            'computer_architecture': [
                'ASPLOS',
                'ASPLOS (1)',
                'ASPLOS (2)',
                'ASPLOS (3)',
                'ISCA',
                'MICRO',
                'MICRO (1)',
                'MICRO (2)',
                'HPCA'
            ],
            'computer_networks': [
                'SIGCOMM',
                'NSDI',
                'CONEXT'
            ],
            'computer_security': [
                'CCS',
                'ACM Conference on Computer and Communications Security',
                'ACM CCS',
                'USENIX Security',
                'USENIX Security Symposium',
                'NDSS',
                'IEEE Symposium on Security and Privacy',
                'IEEE Security and Privacy'
            ],
            'databases': [
                'SIGMOD',
                'SIGMOD Conference',
                'VLDB',
                'ICDE',
                'PODS'
            ],
            'sys_design': ['DAC', 'ICCAD'],
            'embedded_and_real_time': [
                'RTAS',
                'RTSS'
            ],
            'high_performance_computing': [
                'Supercomputing',
                'HPDC',
                'ICS',
                'HPDC'
            ],
            'mobile_computing': [
                'MobiSys',
                'MobiCom',
                'SenSys',
                'IPSN'
            ],
            'measurement_and_performance_analysis': [
                'IMC',
                'Sigmetrics'
            ],
            'operating_systems': [
                'SOSP',
                'OSDI',
                'EuroSys',
                'USENIX Annual Technical Conference',
                'USENIX ATC'
                'USENIX FAST',
                'FAST'
            ],
            'programming_languages': [
                'PLDI',
                'POPL',
                'OOPSLA'
            ],
            'software_engineering': [
                'ASE',
                'FSE',
                'SIGSOFT FSE',
                'ESEC/SIGSOFT FSE',
                'ICSE',
                'ICSE (1)',
                'ICSE (2)'
            ],
            'distributed_systems_and_dependability': [
                'DISC',
                'DSN',
                'ICDCS',
                'PODC'
            ]
        }

    def categorize_venue(self, venue: str) -> str | None:
        if not venue:
            return None

        # Check if venue is a list and convert it to a string
        if isinstance(venue, list):
            venue = ', '.join(venue)

        for area, confs in self.area_to_conference_map.items():
            for conf in confs:
                if venue.casefold() == conf.casefold():
                    return area

        return None


categorize_venue = CategorizeVenue()
