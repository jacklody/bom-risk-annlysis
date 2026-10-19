"""
型号前缀 → 品牌反查规则
用于在BOM物料的品牌字段缺失或不准确时，通过型号前缀识别品牌
"""

# (前缀, 品牌标准名) - 按优先级排序，较长的前缀先匹配
PART_NUMBER_PREFIX_TO_BRAND = [
    # 圣邦微 SGMicro
    ("SGM721", "圣邦微/SGMICRO"),
    ("SGM", "圣邦微/SGMICRO"),
    ("SD76", "圣邦微/SGMICRO"),  # SD76xx 是圣邦微的运放
    ("SD81", "圣邦微/SGMICRO"),
    ("SD82", "圣邦微/SGMICRO"),
    # ST
    ("STM32", "意法半导体/ST"),
    ("STM8", "意法半导体/ST"),
    ("STP", "意法半导体/ST"),
    ("STD", "意法半导体/ST"),
    ("L298", "意法半导体/ST"),
    # TI
    ("TPS", "德州仪器/TI"),
    ("TLV", "德州仪器/TI"),
    ("TPA", "德州仪器/TI"),
    ("LMV", "德州仪器/TI"),
    ("LM358", "德州仪器/TI"),
    ("LM393", "德州仪器/TI"),
    ("LMR", "德州仪器/TI"),
    ("TMS320", "德州仪器/TI"),
    ("SN74", "德州仪器/TI"),
    # NXP
    ("MK", "恩智浦/NXP"),
    ("LPC", "恩智浦/NXP"),
    ("PCA", "恩智浦/NXP"),
    ("MC9S", "恩智浦/NXP"),
    # Microchip
    ("PIC", "微芯/Microchip"),
    ("ATMEGA", "微芯/Microchip"),
    ("ATTINY", "微芯/Microchip"),
    ("AT24", "微芯/Microchip"),
    # 兆易创新 GD
    ("GD32", "兆易创新/GigaDevice"),
    ("GD25", "兆易创新/GigaDevice"),
    # Vishay
    ("SI24", "Vishay"),
    ("SIR", "Vishay"),
    # Nexperia (PMEG, PMOS, BC, BAT, BAS, BC8, PUMB)
    ("PMEG", "Nexperia"),
    ("PMV", "Nexperia"),
    ("PMSS", "Nexperia"),
    # Diodes
    ("DMG", "Diodes"),
    ("DMP", "Diodes"),
    ("DMN", "Diodes"),
    ("AP1117", "Diodes"),
    ("AP2127", "Diodes"),
    # Infineon
    ("BSC", "英飞凌/Infineon"),
    ("BSP", "英飞凌/Infineon"),
    ("IRFR", "英飞凌/Infineon"),
    ("IRFL", "英飞凌/Infineon"),
    ("IRLR", "英飞凌/Infineon"),
    ("IRF", "英飞凌/Infineon"),
    # ON Semi
    ("FDV", "安森美/ON"),
    ("FDS", "安森美/ON"),
    ("FDN", "安森美/ON"),
    ("NCV", "安森美/ON"),
    ("NCP", "安森美/ON"),
    # ADI
    ("ADM", "ADI"),
    ("AD8", "ADI"),
    ("ADA", "ADI"),
    # Murata
    ("GRM", "村田/Murata"),
    ("LQM", "村田/Murata"),
    # Samsung Electro
    # ("CL", "三星电机/SEMCO"),  # CL前缀太通用，禁用
    # Yageo - CC/RC前缀太通用，多家厂商共用同样规格命名，禁用
    # ("CC0", "国巨/Yageo"),
    # ("RC0402", "国巨/Yageo"),
    # ("RC0603", "国巨/Yageo"),
    # ("RC0805", "国巨/Yageo"),
    # ("RC1206", "国巨/Yageo"),
    # TDK
    ("CGA", "TDK"),
    ("MMZ", "TDK"),
    # AVX
    ("TAJ", "AVX"),  # TAJ系列钽电容
    # 3PEAK
    ("TP", "3PEAK"),  # TP24xx等运放
    # 矽力杰 Silergy
    ("SY8", "矽力杰/Silergy"),
    # MPS
    ("MP2", "芯源/MPS"),
    # 长电
    ("CJ7", "长电/CJ"),
    # 强茂
    ("SK", "强茂/Panjit"),
    # 韦尔
    ("WST", "韦尔/WillSemi"),
    # 兴海容/华润微
    ("CMC", "华润微/CR Micro"),
    # 国产MOS 新洁能
    ("NCE", "新洁能/NCEPower"),
    ("NTU", "新洁能/NCEPower"),
    # 力特
    ("0451", "力特/Littelfuse"),
    ("0452", "力特/Littelfuse"),
]


def infer_brand_from_part_number(part_number: str) -> str | None:
    """根据型号前缀推断品牌"""
    if not part_number:
        return None
    pn = part_number.upper().strip()
    for prefix, brand in PART_NUMBER_PREFIX_TO_BRAND:
        if pn.startswith(prefix.upper()):
            return brand
    return None
