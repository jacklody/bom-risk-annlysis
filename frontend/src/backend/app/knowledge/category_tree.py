"""
品类层级树：从大类到细分类目的树状结构
用于支持"品类波及"的向上/同级传播
"""

CATEGORY_TREE = {
    "被动元件": {
        "children": {
            "电容器": {
                "children": {
                    "MLCC": {
                        "children": {
                            "MLCC高容": {},
                            "MLCC中低压": {},
                            "MLCC高压": {},
                        }
                    },
                    "钽电容": {},
                    "铝电解电容": {},
                    "薄膜电容": {},
                }
            },
            "电阻器": {
                "children": {
                    "贴片电阻": {},
                    "精密电阻": {},
                    "功率电阻": {},
                }
            },
            "电感器": {},
        }
    },
    "半导体": {
        "children": {
            "MCU/微控制器": {
                "children": {
                    "ARM Cortex-M": {},
                    "RISC-V": {},
                    "8位MCU": {},
                }
            },
            "电源管理IC": {
                "children": {
                    "DC-DC转换器": {},
                    "LDO": {},
                    "PMIC": {},
                }
            },
            "MOSFET": {},
            "存储芯片": {
                "children": {
                    "DRAM": {},
                    "NAND Flash": {},
                    "NOR Flash": {},
                }
            },
            "模拟芯片": {},
            "FPGA/CPLD": {},
        }
    },
    "连接器": {
        "children": {
            "板对板连接器": {},
            "线对板连接器": {},
            "FPC/FFC连接器": {},
            "USB连接器": {},
        }
    },
    "晶振/振荡器": {},
}


def get_category_path(category_name: str) -> list[str]:
    """获取品类从根到叶的路径，如 MLCC高容 -> ['被动元件','电容器','MLCC','MLCC高容']"""

    def search(tree, target, path=None):
        if path is None:
            path = []
        for name, info in tree.items():
            current_path = path + [name]
            if name == target:
                return current_path
            if "children" in info:
                result = search(info["children"], target, current_path)
                if result:
                    return result
        return None

    return search(CATEGORY_TREE, category_name) or [category_name]


def get_sibling_categories(category_name: str) -> list[str]:
    """获取同级品类（品类波及范围）"""
    path = get_category_path(category_name)
    if len(path) < 2:
        return []
    parent = path[-2]

    def find_node(tree, target):
        for name, info in tree.items():
            if name == target:
                return info
            if "children" in info:
                result = find_node(info["children"], target)
                if result:
                    return result
        return None

    node = find_node(CATEGORY_TREE, parent)
    if node and "children" in node:
        return list(node["children"].keys())
    return []


def get_ancestor_categories(category_name: str) -> list[str]:
    """获取所有祖先品类（用于向上匹配，最多返回1级父节点）"""
    path = get_category_path(category_name)
    if len(path) <= 1:
        return []
    return [path[-2]]  # 只返回直接父级
