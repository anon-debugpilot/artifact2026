import sys
import os
import json
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional

from core.debug_engine import DebugEngine
from utils.logger import setup_logger


class RecursiveDebugger:
    def __init__(self, project_id: str, bug_id: str):
        self.project_id = project_id
        self.bug_id = bug_id
        self.logger = setup_logger("DebugPilot")
        
        self.debug_engine = DebugEngine({"project_id": project_id, "bug_id": bug_id})

        self.session_id = self._generate_session_id()
        self.debug_data = {}
    
    def _generate_session_id(self) -> str:
        return f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def initialize(self) -> bool:
        try:
            self.logger.info(f"Initialization: PROJECT_ID={self.project_id}, BUG_ID={self.bug_id}, session={self.session_id}")
            
            # 读入data数据
            data_dir = os.path.join("benchmark", f"{self.project_id}_{self.bug_id}")
            
            if not os.path.exists(data_dir):
                self.logger.error(f"Data directory not found: {data_dir}")
                return False
            
            # 读取四个JSON文件
            try:
                with open(os.path.join(data_dir, "call_info.json"), 'r', encoding='utf-8') as f:
                    call_info = json.load(f)
                
                with open(os.path.join(data_dir, "code_info.json"), 'r', encoding='utf-8') as f:
                    code_info = json.load(f)
                
                with open(os.path.join(data_dir, "start_info.json"), 'r', encoding='utf-8') as f:
                    start_info = json.load(f)
                
                # with open(os.path.join(data_dir, "complete_trace.json"), 'r', encoding='utf-8') as f:
                #     complete_trace = json.load(f)

                with open(os.path.join(data_dir, "original.json"), 'r', encoding='utf-8') as f:
                    original = json.load(f)

                with open(os.path.join(data_dir, "trace_fix.json"), 'r', encoding='utf-8') as f:
                    trace_fix = json.load(f)
                
                # 将数据存储到debug_data中
                self.debug_data = {
                    "call_info": call_info,
                    "code_info": code_info,
                    "start_info": start_info,
                    # "complete_trace": complete_trace,
                    "original": original,
                    "trace_fix": trace_fix
                }
                
                self.logger.info(f"Successfully loaded data files from {data_dir}")
                self.logger.info(f"Call info entries: {len(call_info)}")
                self.logger.info(f"Code info methods: {len(code_info)}")
                # self.logger.info(f"Complete trace entries: {len(complete_trace)}")
                self.logger.info(f"Original entries: {len(original)}")
                self.logger.info(f"Trace Fix: {len(trace_fix)}")
                self.logger.info(f"Test unit: {start_info.get('test_unit', 'N/A')}")
                
            except FileNotFoundError as e:
                self.logger.error(f"Required data file not found: {e}")
                return False
            except json.JSONDecodeError as e:
                self.logger.error(f"Invalid JSON format in data file: {e}")
                return False

            self.logger.info("Initialization complete")
            return True
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {str(e)}")
            return False
    
    def recursive_debug(self, debug_state=None, selected=None) -> Dict[str, Any]:
        try:
            self.logger.info("Start Debugging...")
            
            debug_result = self.debug_engine.start_debugging(
                debug_data=self.debug_data,
                debug_state=debug_state,
                selected=selected
            )
            
            return debug_result
            
        except Exception as e:
            self.logger.error(f"Debugging failed: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def run(self, debug_state, selected=None) -> Dict[str, Any]:
        try:
            if not self.initialize():
                return {"status": "error", "message": "Initialization failed"}
            
            debug_result = self.recursive_debug(debug_state, selected)
            return debug_result
            
        except Exception as e:
            self.logger.error(f"Error: {str(e)}")
            return {"status": "error", "message": str(e)}


def main():
    parser = argparse.ArgumentParser(description='DebugPilot - Recursive Debugging Tool')
    parser.add_argument('project_id', help='Project identifier')
    parser.add_argument('bug_id', help='Bug identifier')
    parser.add_argument('reliable_state', nargs='?', help='Reliable state (4 integers separated by commas, e.g., "1,1,1,1")')
    parser.add_argument('-s', '--selected', type=int, default=None, help='Selected parameter (default: -1)')
    
    args = parser.parse_args()
    
    project_id = args.project_id
    bug_id = args.bug_id
    selected = args.selected
    
    # 解析 reliable_state 参数
    reliable_state = None
    if args.reliable_state:
        try:
            # 将字符串按逗号分割并转换为整数数组
            state_parts = args.reliable_state.split(',')
            if len(state_parts) != 4:
                print("Error: reliable_state must contain exactly 4 integers separated by commas")
                print("Example: '1,1,1,1'")
                sys.exit(1)
            
            reliable_state = [int(part.strip()) for part in state_parts]
            print(f"Using reliable_state: {reliable_state}")
            
        except ValueError as e:
            print(f"Error: Invalid reliable_state format. All values must be integers: {e}")
            print("Example: '1,1,1,1'")
            sys.exit(1)
    
    # 增加一个可选的参数-s --selected, type为int，默认为-1
    # 这个参数将被传递至debug_engine.start_debugging

    debugger = RecursiveDebugger(project_id, bug_id)
    result = debugger.run(reliable_state, selected)
    
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
