from enum import Enum


class StationMapping(Enum):
    Nangang = 1
    Taipei = 2
    Banqiao = 3
    Taoyuan = 4
    Hsinchu = 5
    Miaoli = 6
    Taichung = 7
    Changhua = 8
    Yunlin = 9
    Chiayi = 10
    Tainan = 11
    Zuouing = 12


class TicketType(Enum):
    ADULT = 'F'
    CHILD = 'H'
    DISABLED = 'W'
    ELDER = 'E'
    COLLEGE = 'P'


class SeatPrefer(Enum):
    NONE = '0'
    WINDOW = '1'
    AISLE = '2'


class SearchType(Enum):
    TIME = 'radio17'
    TRAIN_ID = 'radio19'


class TripType(Enum):
    SINGLE = 0
    ROUND = 1
