"""统一配置加载，所有模块从这里拿路径和参数"""
import yaml
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_cache = {}


def _load(name):
    if name not in _cache:
        p = _ROOT / "config" / f"{name}.yaml"
        with open(p, 'r', encoding='utf-8') as f:
            _cache[name] = yaml.safe_load(f)
    return _cache[name]


def settings():
    return _load("settings")

def accounts():
    return _load("accounts")

def policy():
    return _load("task_policy")

def paths(section=None):
    """获取模板路径，section 如 'transport.birds.bird_451'"""
    data = _load("paths")
    if section is None:
        return data
    keys = section.split('.')
    for k in keys:
        data = data[k]
    return data


def resolve(template_key):
    """
    快捷方法：paths.yaml 中的 key → 绝对路径
    用法: resolve('daily.shop.collect') → 'F:/XYC/templates/daily/shangdian.png'
    """
    rel = paths(template_key)
    p = _ROOT / rel
    return str(p)