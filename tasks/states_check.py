from pathlib import Path

def check_config(txt_path="tasks/states.txt", auto_fix=False):
    """
    检测 txt 配置与实际文件的差异
    
    Args:
        txt_path: 配置文件路径
        auto_fix: 是否自动补全缺失配置
    """
    
    base_dir = Path(txt_path).resolve().parent.parent
    states_dir = base_dir / "tasks" / "states"
    change_dir = base_dir / "tasks" / "states_change"
    
    # 从 txt 提取已配置的文件名
    txt_states = set()
    txt_change = set()
    
    with open(txt_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.split('#')[0].strip()
            if not line or '=' not in line:
                continue
            key, val = [x.strip() for x in line.split('=')]
            val = val.strip('"')
            file_name = Path(val).stem
            
            parts = key.split('_')
            if len(parts) == 1:
                txt_states.add(file_name)
            else:
                txt_change.add(file_name)
    
    # 扫描实际文件
    real_states = {f.stem for f in states_dir.glob("*.png")} if states_dir.exists() else set()
    real_change = {f.stem for f in change_dir.glob("*.json")} if change_dir.exists() else set()
    
    # 打印差异
    has_diff = False
    
    if txt_states - real_states:
        has_diff = True
        print("❌ txt 有但缺少 .png:")
        for name in sorted(txt_states - real_states):
            print(f"   {name}.png")
    
    if real_states - txt_states:
        has_diff = True
        print("⚠️ 有 .png 但 txt 未配置:")
        for name in sorted(real_states - txt_states):
            print(f"   {name}.png")
    
    if txt_change - real_change:
        has_diff = True
        print("❌ txt 有但缺少 .json:")
        for name in sorted(txt_change - real_change):
            print(f"   {name}.json")
    
    if real_change - txt_change:
        has_diff = True
        print("⚠️ 有 .json 但 txt 未配置:")
        for name in sorted(real_change - txt_change):
            print(f"   {name}.json")
    
    if not has_diff:
        print("✅ 全部匹配")
        return
    
    # 可选：自动补全
    if not auto_fix:
        return
    
    missing_states = real_states - txt_states
    missing_change = real_change - txt_change
    
    if missing_states or missing_change:
        with open(txt_path, 'a', encoding='utf-8') as f:
            if missing_states:
                f.write("\n# ===== 自动添加 =====\n")
                for name in sorted(missing_states):
                    f.write(f'{name} = "tasks/states/{name}"\n')
                print(f"✅ 已添加 {len(missing_states)} 个 check 配置")
            
            if missing_change:
                f.write("\n# ===== 自动添加（需改key）=====\n")
                for name in sorted(missing_change):
                    f.write(f'# TODO_TODO_01 = "tasks/states_change/{name}"\n')
                print(f"✅ 已添加 {len(missing_change)} 个 change 配置")


if __name__ == "__main__":
    # 只检测，不修改
    check_config("tasks/states.txt")
    
    # 检测并自动补全
    # check_config("tasks/states.txt", auto_fix=True)