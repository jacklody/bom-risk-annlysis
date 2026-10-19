"""
品牌 → 主要品类映射表
用于：(1) 事件匹配时识别品牌对应的品类范围
       (2) BOM物料模糊匹配时做品牌品类交叉验证
"""

# 品牌标准名称 → (品牌别名列表, 主要品类列表)
BRAND_CATEGORY_MAP = {
    "村田/Murata": (["村田", "murata", "Murata"], ["MLCC", "电感器", "滤波器", "连接器"]),
    "三星电机/SEMCO": (["三星电机", "SEMCO", "Samsung Electro-Mechanics", "samsung电机"],
                      ["MLCC", "贴片电阻"]),
    "国巨/Yageo": (["国巨", "yageo", "Yageo"], ["MLCC", "贴片电阻"]),
    "太阳诱电/Taiyo": (["太阳诱电", "taiyo yuden", "Taiyo Yuden", "taiyo"],
                       ["MLCC", "电感器"]),
    "TDK": (["TDK", "tdk"], ["MLCC", "电感器", "滤波器"]),
    "意法半导体/ST": (["ST", "意法半导体", "stmicroelectronics", "STM", "stm"],
                     ["MCU/微控制器", "MOSFET", "电源管理IC", "模拟芯片"]),
    "德州仪器/TI": (["TI", "德州仪器", "Texas Instruments", "ti"],
                    ["电源管理IC", "模拟芯片", "MCU/微控制器"]),
    "英飞凌/Infineon": (["英飞凌", "infineon", "Infineon"],
                        ["MOSFET", "IGBT", "MCU/微控制器", "电源管理IC"]),
    "恩智浦/NXP": (["NXP", "恩智浦", "nxp"], ["MCU/微控制器", "电源管理IC"]),
    "瑞萨/Renesas": (["瑞萨", "renesas", "Renesas"],
                     ["MCU/微控制器", "电源管理IC", "模拟芯片"]),
    "微芯/Microchip": (["微芯", "microchip", "Microchip"],
                       ["MCU/微控制器", "存储芯片", "模拟芯片"]),
    "美光/Micron": (["美光", "micron", "Micron"], ["DRAM", "NAND Flash"]),
    "三星/Samsung": (["三星", "samsung", "Samsung"], ["DRAM", "NAND Flash"]),
    "SK海力士": (["SK海力士", "hynix", "Hynix", "SK Hynix", "sk hynix"],
                 ["DRAM", "NAND Flash"]),
    "泰科/TE": (["泰科", "TE", "TE Connectivity", "te connectivity"],
                ["连接器", "继电器"]),
    "莫仕/Molex": (["莫仕", "molex", "Molex"], ["连接器"]),
    "广濑/Hirose": (["广濑", "hirose", "Hirose"], ["连接器", "FPC/FFC连接器"]),
    "台积电/TSMC": (["台积电", "tsmc", "TSMC"], ["半导体"]),
    "联电/UMC": (["联电", "umc", "UMC"], ["半导体"]),
    "中芯国际/SMIC": (["中芯国际", "smic", "SMIC"], ["半导体"]),
    "AVX": (["AVX", "avx"], ["MLCC", "钽电容"]),
    "松下/Panasonic": (["松下", "panasonic", "Panasonic"], ["MLCC", "薄膜电容", "安规电容", "贴片电阻", "电感器"]),
    "安森美/ON": (["安森美", "ON", "onsemi", "ON Semiconductor"],
                  ["MOSFET", "电源管理IC", "模拟芯片"]),
    "ADI": (["ADI", "adi", "Analog Devices"], ["模拟芯片", "电源管理IC"]),
    "赛灵思/Xilinx": (["赛灵思", "xilinx", "Xilinx", "AMD"],
                      ["FPGA/CPLD"]),
    "英特尔/Altera": (["英特尔", "intel", "Intel", "altera", "Altera"],
                      ["FPGA/CPLD"]),
    # === 被动元件厂商 ===
    "华新科/Walsin": (["华新科", "华科", "walsin", "Walsin"], ["MLCC", "贴片电阻"]),
    "风华/Fenghua": (["风华", "风华高科", "fenghua", "Fenghua"], ["MLCC", "贴片电阻", "电感器"]),
    "厚声/UniOhm": (["厚声", "uniohm", "UniOhm"], ["贴片电阻"]),
    "旺诠/Ralec": (["旺诠", "ralec", "Ralec"], ["贴片电阻"]),
    "大毅/TA-I": (["大毅", "TA-I", "tai"], ["贴片电阻"]),
    "顺络/Sunlord": (["顺络", "sunlord", "Sunlord"], ["电感器", "磁珠"]),
    "奇力新/Chilisin": (["奇力新", "chilisin", "Chilisin"], ["电感器"]),
    # === 半导体厂商 ===
    "圣邦微/SGMICRO": (["圣邦微", "圣邦", "sgmicro", "SGMICRO", "SGM"], ["电源管理IC", "模拟芯片", "运放"]),
    "纳芯微/Novosense": (["纳芯微", "novosense", "Novosense"], ["模拟芯片", "隔离芯片"]),
    "3PEAK": (["3peak", "3PEAK", "思瑞浦"], ["运放", "模拟芯片"]),
    "兆易创新/GigaDevice": (["兆易创新", "GD", "gigadevice", "GigaDevice"], ["MCU/微控制器", "存储芯片"]),
    "Diodes": (["DIODES", "Diodes", "diodes", "美台"], ["MOSFET", "二极管", "模拟芯片"]),
    "强茂/Panjit": (["强茂", "panjit", "Panjit"], ["MOSFET", "二极管"]),
    "长电/CJ": (["长电", "CJ", "江苏长电"], ["MOSFET", "二极管", "ESD保护"]),
    "MCC": (["MCC", "mcc", "美微科"], ["MOSFET", "二极管"]),
    "Vishay": (["Vishay", "vishay", "威世"], ["MOSFET", "二极管", "电阻"]),
    "Nexperia": (["Nexperia", "nexperia", "安世"], ["MOSFET", "二极管", "逻辑芯片"]),
    "晶导微/JDM": (["晶导微", "JDM", "jdm"], ["二极管", "MOSFET"]),
    # === 连接器 ===
    "维峰/Wcon": (["维峰", "wcon", "Wcon"], ["连接器"]),
    "星坤/XKB": (["星坤", "XKB", "xkb"], ["连接器"]),
    # === 电解电容 ===
    "尼吉康/Nichicon": (["尼吉康", "nichicon", "Nichicon"], ["铝电解电容"]),
    "红宝石/Rubycon": (["红宝石", "rubycon", "Rubycon"], ["铝电解电容"]),
    "黑金刚/NCC": (["黑金刚", "Nippon", "Chemi-Con", "NCC"], ["铝电解电容"]),
    # === 其他 ===
    "EPCOS/TDK": (["EPCOS", "epcos"], ["MLCC", "压敏电阻", "电感器"]),
    "法拉/Farad": (["法拉", "farad", "Farad"], ["薄膜电容", "安规电容"]),
    "三莹/Samyoung": (["三莹", "samyoung", "Samyoung"], ["铝电解电容"]),
    "力特/Littelfuse": (["力特", "littelfuse", "Littelfuse"], ["保险丝", "ESD保护"]),
    "贝特/Better": (["贝特", "better", "贝特电子"], ["保险丝"]),
    "芯源/MPS": (["芯源", "MPS", "mps", "芯源半导体"], ["电源管理IC", "DC-DC"]),
    "矽力杰/Silergy": (["矽力杰", "silergy", "Silergy"], ["电源管理IC"]),
    "上海贝岭/Belling": (["上海贝岭", "贝岭", "belling", "Belling"], ["电源管理IC", "模拟芯片"]),
    "晶丰明源/BPS": (["晶丰明源", "BPS", "bps"], ["电源管理IC", "LED驱动"]),
    "士兰微/Silan": (["士兰微", "silan", "Silan"], ["MOSFET", "IGBT", "电源管理IC"]),
    "华润微/CR Micro": (["华润微", "华润", "CR Micro"], ["MOSFET"]),
    "韦尔/WillSemi": (["韦尔", "willsemi", "WillSemi"], ["MOSFET", "ESD保护"]),
    "乐山无线电/LRC": (["乐山", "LRC", "lrc", "乐山无线电"], ["二极管", "MOSFET"]),
    "扬杰/Yangjie": (["扬杰", "yangjie", "Yangjie"], ["二极管", "MOSFET"]),
    "捷捷微/JJM": (["捷捷微", "JJM", "jjm"], ["MOSFET", "晶闸管"]),
    "上海芯导/Precision": (["芯导", "Precision", "prisemi"], ["ESD保护", "MOSFET"]),
    "芯朋微/Chipown": (["芯朋微", "chipown", "Chipown"], ["电源管理IC"]),
    "南芯/Southchip": (["南芯", "southchip", "Southchip"], ["电源管理IC", "快充芯片"]),
    "英集芯/Injoinic": (["英集芯", "injoinic", "Injoinic"], ["电源管理IC", "快充芯片"]),
    "新洁能/NCEPower": (["新洁能", "NCE", "nce", "NCEPower"], ["MOSFET"]),
    "中微创芯/CMIC": (["中微创芯", "CMIC", "cmic", "琴芯微"], ["IPM", "功率模块"]),
    "三环/Sanhuan": (["三环", "sanhuan", "Sanhuan"], ["MLCC", "贴片电容"]),
    "奥伦德/Orpc": (["奥伦德", "orpc", "Orpc"], ["光耦", "光电器件"]),
    "乐山希尔/Shr": (["乐山希尔", "希尔", "SHR", "shr"], ["二极管", "桥堆"]),
    "敏芯微/Memsic": (["敏芯微", "memsic", "Memsic"], ["MEMS传感器"]),
}

# 品牌别名 → 标准名称 快查表
ALIAS_TO_BRAND: dict[str, str] = {}
for std_name, (aliases, _) in BRAND_CATEGORY_MAP.items():
    for alias in aliases:
        ALIAS_TO_BRAND[alias.lower()] = std_name
    ALIAS_TO_BRAND.setdefault(std_name.lower(), std_name)


def normalize_brand(raw_brand: str) -> str | None:
    """标准化品牌名称"""
    if not raw_brand:
        return None
    lower = raw_brand.strip().lower()
    return ALIAS_TO_BRAND.get(lower)


def get_brand_categories(brand: str) -> list[str]:
    """获取某品牌涉及的主要品类"""
    if not brand:
        return []
    brand_key = ALIAS_TO_BRAND.get(brand.lower())
    if not brand_key:
        return []
    _, categories = BRAND_CATEGORY_MAP.get(brand_key, ([], []))
    return categories
