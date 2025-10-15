#!/usr/bin/env python3
import sys
import os
import json
import re
from collections import defaultdict
from typing import Dict, List, Any


def parse_state_filename(filename: str) -> tuple:
    match = re.match(r'state_(\d+)_(\d+)_(\d+)_(\d+)\.json', filename)
    if match:
        return tuple(map(int, match.groups()))
    return None


def load_state_files(result_dir: str) -> Dict[int, Dict[int, List[Dict]]]:
    state_files = {}
    
    if not os.path.exists(result_dir):
        print(f"error: {result_dir} does not exist")
        return {}
    
    for filename in os.listdir(result_dir):
        if filename.startswith('state_') and filename.endswith('.json'):
            parsed = parse_state_filename(filename)
            if parsed:
                a, b, c, d = parsed
                filepath = os.path.join(result_dir, filename)
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        data['indices'] = {'a': a, 'b': b, 'c': c, 'd': d}
                        data['filename'] = filename
                        
                        if a not in state_files:
                            state_files[a] = {}
                        if b not in state_files[a]:
                            state_files[a][b] = []
                        state_files[a][b].append(data)
                except Exception as e:
                    print(f"error: {filename}: {e}")
    
    return state_files


def count_dividing_phases(method_data: Dict[int, List[Dict]]) -> int:
    return len(method_data.keys())


def extract_method_info(state_data: Dict) -> Dict[str, Any]:
    result = state_data.get('result', {})
    method_name = result.get('method_name', '')
    
    if '#' in method_name:
        method_part = method_name.split('#')[0]
        simple_name = method_part.split('.')[-1] + '#' + method_name.split('#')[1]
        if method_part.split('.')[-1] == "<init>":
            simple_name = method_part.split('.')[-2] + '.' + simple_name
    else:
        simple_name = method_name.split('.')[-1] if '.' in method_name else method_name
    
    return {
        'full_name': method_name,
        'simple_name': simple_name,
        'start_line': result.get('start_line', 0),
        'end_line': result.get('end_line', 0)
    }


def get_block_info_from_state(state_data: Dict) -> List[Dict]:
    result = state_data.get('result', {})
    blocks = result.get('list', {}).get('blocks', [])
    return blocks


def extract_locating_options(phase_states: List[Dict], selected_blocks: List[Dict], selected_id: int, call_info_path: str = None) -> List[Dict]:
    options = []
    
    call_info_data = []
    if call_info_path and os.path.exists(call_info_path):
        try:
            with open(call_info_path, 'r', encoding='utf-8') as f:
                call_info_data = json.load(f)
        except Exception as e:
            print(f"警告: 无法读取call_info.json: {e}")
    
    selected_block = None
    for block in selected_blocks:
        if block.get('id') == selected_id:
            selected_block = block
            break
    
    if selected_block:
        local_option = {
            "id": 0,
            "start_line": selected_block.get('start_line'),
            "end_line": selected_block.get('end_line'),
            "comment": "Local Code",
            "status": 0
        }
        
        fault_value = 0
        for state in phase_states:
            result = state.get('result', {})
            location_info = result.get('location', {})
            if 'fault' in location_info:
                fault_value = location_info.get('fault', 0)
                break
        
        if fault_value == 1:
            local_option["status"] = 1
            for state in phase_states:
                result = state.get('result', {})
                location_info = result.get('location', {})
                if 'analysis' in location_info:
                    local_option["summary"] = location_info.get('analysis', '')
                    break
        
        for state in phase_states:
            result = state.get('result', {})
            if 'selected' in result and 'execution_first' in result['selected']:
                local_option["trace"] = result['selected']['execution_first']
                break
        
        options.append(local_option)
    
    for state in phase_states:
        indices = state['indices']
        b, c, d = indices['b'], indices['c'], indices['d']
        
        if c == 2 and d == 1:
            result = state.get('result', {})
            location_info = result.get('location', {})
            
            messages = state.get('messages', [])
            record_calls = []
            
            for msg in messages:
                if msg.get('role') == 'user':
                    content = msg.get('content', '')
                    import re
                    record_match = re.search(r'<record>\s*(.*?)\s*</record>', content, re.DOTALL)
                    if record_match:
                        record_content = record_match.group(1).strip()
                        for line in record_content.split('\n'):
                            line = line.strip()
                            if ':' in line:
                                parts = line.split(':', 1)
                                if len(parts) == 2:
                                    call_id = parts[0].strip()
                                    method_name = parts[1].strip()
                                    record_calls.append((call_id, method_name))
            
            for i, (call_id, method_name) in enumerate(record_calls):
                if '#' in method_name:
                    simple_method = method_name.split('.')[-1]
                else:
                    simple_method = method_name.split('.')[-1] if '.' in method_name else method_name
                
                call_option = {
                    "id": i + 1,
                    "start_line": selected_block.get('start_line') if selected_block else 0,
                    "end_line": selected_block.get('end_line') if selected_block else 0,
                    "comment": f"Call: {simple_method}",
                    "status": 1 if location_info.get('details') == int(call_id) else 0
                }
                
                call_trace_id = None
                for call_info in call_info_data:
                    if call_info.get('call_trace') == int(call_id):
                        call_trace_id = call_info.get('start', 1) - 1  # start - 1
                        break
                
                if call_trace_id is not None:
                    call_option["trace"] = call_trace_id
                elif selected_block and 'trace' in local_option:
                    call_option["trace"] = local_option["trace"]
                
                if call_option["status"] == 1:
                    call_option["summary"] = location_info.get('analysis', '')
                
                options.append(call_option)
            
            break
    
    return options


def extract_selected_option_info(phase_states: List[Dict]) -> Dict[str, Any]:
    selected_info = {}
    
    for state in phase_states:
        result = state.get('result', {})
        indices = state['indices']
        b, c, d = indices['b'], indices['c'], indices['d']
        
        if c == 1 and d == 2:
            selected_result = result.get('selected', '')
            import re
            match = re.search(r'ID:\s*(\d+)', selected_result)
            if match:
                selected_info['selected_id'] = int(match.group(1))
        
        elif c == 1 and d == 3:
            presentation = result.get('presentation', {})
            if presentation:
                selected_info['signature'] = presentation.get('signature', '').rstrip('"')
        
        elif b == 2 and c == 1 and d == 1:
            phase_result = result.get('list', {})
            if phase_result:
                selected_info['phase_start_line'] = phase_result.get('start_line')
                selected_info['phase_end_line'] = phase_result.get('end_line')
                selected_info['phase_description'] = phase_result.get('description', '')
        
        elif c == 1 and d == 5:
            spec = result.get('specification', {})
            if spec:
                selected_info['specification'] = spec
        
        elif c == 1 and d == 6:
            oracle_data = result.get('oracle', {})
            if oracle_data and 'oracle' in oracle_data:
                selected_info['oracle'] = oracle_data['oracle']
        
        elif c == 1 and d == 7:
            match_data = result.get('match', {})
            if match_data:
                selected_info['match'] = match_data.get('match', [])
                selected_info['summary'] = match_data.get('summary', '')
                selected_info['consistent'] = match_data.get('consistent', 0.0)
                
        if 'selected' in result and 'execution_first' in result['selected']:
            selected_info['trace'] = result['selected']['execution_first']
    
    return selected_info


def create_plan_structure(method_id: int, method_data: Dict[int, List[Dict]], benchmark_dir: str = None) -> Dict[str, Any]:
    first_phase_states = list(method_data.values())[0]
    method_info = extract_method_info(first_phase_states[0])
    
    src_path = ""
    if benchmark_dir:
        code_info_path = os.path.join(benchmark_dir, "code_info.json")
        if os.path.exists(code_info_path):
            try:
                with open(code_info_path, 'r', encoding='utf-8') as f:
                    code_info_data = json.load(f)
                    full_method_name = method_info['full_name']
                    if full_method_name in code_info_data:
                        src_path = code_info_data[full_method_name].get('src_path', '')
            except Exception as e:
                print(f"error: {e}")
    
    dividing_count = count_dividing_phases(method_data)
    
    plan = []
    
    previous_signatures = []
    
    for i, (phase_id, phase_states) in enumerate(sorted(method_data.items())):
        blocks = get_block_info_from_state(phase_states[0])
        selected_info = extract_selected_option_info(phase_states)
        
        start_line = selected_info.get('phase_start_line', method_info['start_line'])
        end_line = selected_info.get('phase_end_line', method_info['end_line'])
        
        # print(f"Phase {phase_id}: {len(blocks)} blocks, selected_id: {selected_info.get('selected_id', 'N/A')}")
        # print(f"  Range: {start_line}-{end_line}")
        # print(f"  Signature: {selected_info.get('signature', 'N/A')}")
        
        options = []
        for block in blocks:
            option = {
                "id": block.get('id', 0),
                "start_line": block.get('start_line', start_line),
                "end_line": block.get('end_line', end_line),
                "comment": block.get('comment', '').rstrip(',').rstrip('"'),
                "status": 0
            }
            
            if option["id"] == selected_info.get('selected_id'):
                option["status"] = 1
                
                if 'trace' in selected_info:
                    option["trace"] = selected_info['trace']
                
                if 'specification' in selected_info:
                    option["specification"] = selected_info['specification']
                
                if 'oracle' in selected_info:
                    option["oracle"] = selected_info['oracle']
                
                if 'match' in selected_info:
                    option["match"] = selected_info['match']
                
                if 'summary' in selected_info:
                    option["summary"] = selected_info['summary']
                
                if 'consistent' in selected_info:
                    option["consistent"] = selected_info['consistent']
                
            options.append(option)
        
        if i == 0:
            focus_name = "Method"
        else:
            if len(previous_signatures) >= i:
                prev_signature = previous_signatures[i - 1]
                prev_phase_states = list(method_data.values())[i - 1]
                prev_selected_info = extract_selected_option_info(prev_phase_states)
                prev_selected_id = prev_selected_info.get('selected_id', 0)
                
                if i == 1:
                    focus_name = f"Block {prev_selected_id}: {prev_signature}"
                elif i == 2:
                    focus_name = f"Subblock {prev_selected_id}: {prev_signature}"
                else:
                    focus_name = f"Sub{'sub' * (i-2)}block {prev_selected_id}: {prev_signature}"
            else:
                focus_name = f"Block {i}"
        
        if 'signature' in selected_info:
            previous_signatures.append(selected_info['signature'])
        
        plan.append({
            "focus": focus_name,
            "phase": "dividing",
            "start_line": start_line,
            "end_line": end_line,
            "options": options
        })
    
    if previous_signatures:
        last_signature = previous_signatures[-1]
        last_phase_states = list(method_data.values())[-1]
        last_selected_info = extract_selected_option_info(last_phase_states)
        last_selected_id = last_selected_info.get('selected_id', 0)
        
        last_blocks = get_block_info_from_state(last_phase_states[0])
        locating_start_line = method_info['start_line']
        locating_end_line = method_info['end_line']
        
        for block in last_blocks:
            if block.get('id') == last_selected_id:
                locating_start_line = block.get('start_line', method_info['start_line'])
                locating_end_line = block.get('end_line', method_info['end_line'])
                break
        
        call_info_path = os.path.join(benchmark_dir, "call_info.json") if benchmark_dir else None
        locating_options = extract_locating_options(last_phase_states, last_blocks, last_selected_id, call_info_path)
        
        if dividing_count == 1:
            locating_focus = f"Block {last_selected_id}: {last_signature}"
        elif dividing_count == 2:
            locating_focus = f"Subblock {last_selected_id}: {last_signature}"
        else:
            locating_focus = f"Sub{'sub' * (dividing_count-2)}block {last_selected_id}: {last_signature}"
    else:
        locating_focus = "Final Locating"
        locating_start_line = method_info['start_line']
        locating_end_line = method_info['end_line']
        locating_options = []
    
    plan.append({
        "focus": locating_focus,
        "phase": "locating",
        "start_line": locating_start_line,
        "end_line": locating_end_line,
        "options": locating_options
    })
    
    return {
        "method": method_info['simple_name'],
        "src_path": src_path,
        "plan": plan
    }


def generate_debugging_plan(state_files: Dict[int, Dict[int, List[Dict]]], benchmark_dir: str = None) -> List[Dict[str, Any]]:
    debugging_plan = []
    
    for method_id in sorted(state_files.keys()):
        method_data = state_files[method_id]
        plan_entry = create_plan_structure(method_id, method_data, benchmark_dir)
        debugging_plan.append(plan_entry)
    
    return debugging_plan


def print_statistics(state_files: Dict[int, Dict[int, List[Dict]]]):
    for method_id in sorted(state_files.keys()):
        method_data = state_files[method_id]
        first_phase_states = list(method_data.values())[0]
        method_info = extract_method_info(first_phase_states[0])
        dividing_count = count_dividing_phases(method_data)
        
        total_states = sum(len(states) for states in method_data.values())
        
        print(f"Method {method_id}: {method_info['simple_name']}")
        print(f"  - State文件数量: {total_states}")
        print(f"  - Dividing阶段数: {dividing_count}")
        print(f"  - Plan总阶段数: {dividing_count + 1} (包含1个locating)")
        
        for phase_id in sorted(method_data.keys()):
            phase_states = method_data[phase_id]
            filenames = [s['filename'] for s in phase_states]
            print(f"  - Phase {phase_id}: {len(filenames)}个文件: {', '.join(sorted(filenames))}")
        print()


def main():
    if len(sys.argv) != 3:
        print("usage: python summary.py <project_name> <project_id>")
        print("e.g.: python summary.py Chart 24")
        sys.exit(1)
    
    project_name = sys.argv[1]
    project_id = sys.argv[2]
    
    project_dir = f"{project_name}_{project_id}"
    result_dir = os.path.join("result", project_dir)
    benchmark_dir = os.path.join("benchmark", project_dir)
    output_file = os.path.join(result_dir, "debugging_plan.json")

    state_files = load_state_files(result_dir)
    
    if not state_files:
        sys.exit(1)
    
    debugging_plan = generate_debugging_plan(state_files, benchmark_dir)
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(debugging_plan, f, indent=4, ensure_ascii=False)
            
    except Exception as e:
        print(f"error: {output_file}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
