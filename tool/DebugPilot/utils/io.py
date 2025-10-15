import json
from typing import Dict, List, Any, Tuple, Optional
from utils.logger import get_logger


class IOExtractor:
    """Input/Output data extractor for trace analysis"""
    
    def __init__(self):
        self.logger = get_logger("io_extractor")
    
    def get_data_dependency_reverse(self, data: List[Dict[str, Any]], current: int, 
                                  write_var: Dict[str, Any], end_id: int) -> int:
        try:
            var_id = write_var.get("id")
            head_id = write_var.get("alias_id")

            for i in range(end_id + 1, len(data) + 1):
                if i - 1 >= len(data):
                    break
                    
                input_list = data[i - 1].get("input", [])
                for input_var in input_list:
                    if input_var.get("depend") != current:
                        continue
                    
                    ivar_id = input_var.get("id")
                    ihead_id = input_var.get("alias_id")

                    if (ivar_id is not None and ivar_id == var_id):
                        return i
                    if (ihead_id is not None and ihead_id == head_id and ihead_id != "-1"):
                        return i
            for i in range(current + 1, end_id):
                input_list = data[i - 1].get("input", [])
                for input_var in input_list:
                    if input_var.get("depend") != current:
                        continue
                    
                    ivar_id = input_var.get("id")
                    ihead_id = input_var.get("alias_id")

                    if (ivar_id is not None and ivar_id == var_id):
                        return i
                    if (ihead_id is not None and ihead_id == head_id and ihead_id != "-1"):
                        return i
            
            return -1
        except Exception as e:
            self.logger.error(f"Error in get_data_dependency_reverse: {str(e)}")
            return -1

    def build_variable_tree(self, variables: List[Dict[str, Any]], parent_depth: int, 
                           start_idx: int) -> Tuple[List[Dict[str, Any]], int]:
        try:
            tree = []
            idx = start_idx
            while idx < len(variables):
                node = variables[idx]
                if node.get("depth", 0) <= parent_depth:
                    break
                
                children, next_idx = self.build_variable_tree(variables, node.get("depth", 0), idx + 1)

                tree.append({"var": node, "children": children})
                idx = next_idx
            return tree, idx
        except Exception as e:
            self.logger.error(f"Error in build_variable_tree: {str(e)}")
            return [], start_idx

    def extract_io_data(self, trace_data: List[Dict[str, Any]], current_call: int, 
                       start_line: int, end_line: int, trace_fix: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        try:
            first_execution = start_line
            last_execution = end_line
            
            if first_execution == -1 or last_execution == -1:
                self.logger.warning(f"Could not find execution range for lines {start_line}-{end_line}")
                return {"block_read": [], "block_write": [], "invalue": "", "outvalue": ""}
            
            block_read = self._extract_block_read(trace_data, first_execution, last_execution, current_call, 3)
            block_write = self._extract_block_write(trace_data, first_execution, last_execution, 10)
            
            if trace_fix:
                trace_fix_read, trace_fix_write = self._process_trace_fix(trace_fix, first_execution, last_execution)
                block_read.extend(trace_fix_read)
                block_write.extend(trace_fix_write)
            
            invalue = self._format_input_values(block_read)
            outvalue = self._format_output_values(block_write)
            
            return {
                "block_read": block_read,
                "block_write": block_write,
                "invalue": invalue,
                "outvalue": outvalue,
                "execution_range": {
                    "first": first_execution,
                    "last": last_execution
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error in extract_io_data: {str(e)}")
            return {"block_read": [], "block_write": [], "invalue": "", "outvalue": ""}

    def _process_trace_fix(self, trace_fix: List[Dict[str, Any]], first_execution: int, 
                          last_execution: int) -> Tuple[List[Tuple[int, Dict[str, Any], int, Dict[str, Any]]], 
                                                       List[Tuple[int, Dict[str, Any], int, Dict[str, Any]]]]:
        try:
            fix_read = []
            fix_write = []
            
            for fix_item in trace_fix:
                trace_id = fix_item.get("trace_id", 0)
                io_type = fix_item.get("io", "")
                var_data = fix_item.get("var", {})
                
                if not (first_execution <= trace_id <= last_execution):
                    continue
                
                var_tree = {"var": var_data, "children": []}
                
                if io_type == "input":
                    fix_read.append((trace_id, var_data, -1, var_tree))
                elif io_type == "output":
                    fix_write.append((trace_id, var_data, -1, var_tree))
            
            return fix_read, fix_write
            
        except Exception as e:
            self.logger.error(f"Error in _process_trace_fix: {str(e)}")
            return [], []

    def _find_first_execution(self, trace_data: List[Dict[str, Any]], current_call: int, 
                             start_line: int, end_line: int) -> int:
        try:
            for i, trace in enumerate(trace_data):
                if trace.get("trace_id", 0) >= current_call:
                    line = trace.get("line", 0)
                    if start_line <= line <= end_line:
                        return trace.get("trace_id", i + 1)
            return -1
        except Exception as e:
            self.logger.error(f"Error in _find_first_execution: {str(e)}")
            return -1

    def _find_last_execution(self, trace_data: List[Dict[str, Any]], current_call: int, 
                            start_line: int, end_line: int) -> int:
        try:
            last_execution = -1
            for i, trace in enumerate(trace_data):
                if trace.get("trace_id", 0) >= current_call:
                    line = trace.get("line", 0)
                    if start_line <= line <= end_line:
                        last_execution = trace.get("trace_id", i + 1)
            return last_execution
        except Exception as e:
            self.logger.error(f"Error in _find_last_execution: {str(e)}")
            return -1

    def _extract_block_read(self, trace_data: List[Dict[str, Any]], begin_id: int, 
                           end_id: int, current_call: int, ex_scope: int) -> List[Tuple[int, Dict[str, Any], int, Dict[str, Any]]]:
        try:
            block_read = []
            depth0 = trace_data[begin_id].get("depth", 0)
            
            for i in range(begin_id, min(len(trace_data) + 1, end_id + 1)):
                if i - 1 >= len(trace_data):
                    break
                    
                trace = trace_data[i - 1]

                if trace.get("depth") - depth0 > ex_scope:
                    continue
                
                for j, read_var in enumerate(trace.get("input", [])):
                    if read_var.get("depth", 0) != 0:
                        continue
                    
                    depend = read_var.get("depend", -1)
                    if depend >= begin_id:
                        continue
                    
                    var_tree, _ = self.build_variable_tree(trace.get("input", []), 
                                                         read_var.get("depth", 0), j + 1)
                    var_tree = {"var": read_var, "children": var_tree}
                    block_read.append((i, read_var, depend, var_tree))
                
                if trace.get("trace_id") == end_id:
                    break
            
            return self._deduplicate_variables(block_read)
            
        except Exception as e:
            self.logger.error(f"Error in _extract_block_read: {str(e)}")
            return []

    def _extract_block_write(self, trace_data: List[Dict[str, Any]], begin_id: int, 
                            end_id: int, ex_scope: int) -> List[Tuple[int, Dict[str, Any], int, Dict[str, Any]]]:
        try:
            block_write = []
            depth0 = trace_data[begin_id].get("depth", 0)
            
            for i in range(begin_id, min(len(trace_data) + 1, end_id + 1)):
                if i - 1 >= len(trace_data):
                    break
                    
                trace = trace_data[i - 1]

                if trace.get("depth") - depth0 > ex_scope:
                    continue
                
                for j, write_var in enumerate(trace.get("output", [])):
                    if write_var.get("depth", 0) != 0:
                        continue
                    
                    depend = write_var.get("reverse", -1)
                    # self.get_data_dependency_reverse(trace_data, i, write_var, end_id)
                    if depend <= end_id:
                    # if depend <= end_id and depend != -1:
                        continue
                    
                    var_tree, _ = self.build_variable_tree(trace.get("output", []), 
                                                         write_var.get("depth", 0), j + 1)
                    var_tree = {"var": write_var, "children": var_tree}
                    block_write.append((i, write_var, depend, var_tree))
                
                if trace.get("trace_id") == end_id:
                    break
            
            return self._deduplicate_variables(block_write)
            
        except Exception as e:
            self.logger.error(f"Error in _extract_block_write: {str(e)}")
            return []

    def _deduplicate_variables(self, variables: List[Tuple[int, Dict[str, Any], int, Dict[str, Any]]]) -> List[Tuple[int, Dict[str, Any], int, Dict[str, Any]]]:
        try:
            unique_variables = []
            seen_ids = set()
            seen_alias = set()
            
            for item in variables:
                var = item[1]
                id_ = var.get("id")
                alias_id = var.get("alias_id")
                
                if id_ in seen_ids:
                    continue
                if alias_id and alias_id != "-1" and alias_id in seen_alias:
                    continue
                
                unique_variables.append(item)
                seen_ids.add(id_)
                if alias_id and alias_id != "-1":
                    seen_alias.add(alias_id)
            
            return unique_variables
        except Exception as e:
            self.logger.error(f"Error in _deduplicate_variables: {str(e)}")
            return variables

    def _format_input_values(self, block_read: List[Tuple[int, Dict[str, Any], int, Dict[str, Any]]]) -> str:
        try:
            input_lines = []
            for item in block_read:
                tree = item[3]
                formatted = self._format_tree_structure(tree, show_values=True)
                input_lines.extend(formatted)
            return "\n".join(input_lines)
        except Exception as e:
            self.logger.error(f"Error in _format_input_values: {str(e)}")
            return ""

    def _format_output_values(self, block_write: List[Tuple[int, Dict[str, Any], int, Dict[str, Any]]]) -> str:
        try:
            output_lines = []
            for item in block_write:
                tree = item[3]
                formatted = self._format_tree_structure(tree, show_values=True)
                output_lines.extend(formatted)
            return "\n".join(output_lines)
        except Exception as e:
            self.logger.error(f"Error in _format_output_values: {str(e)}")
            return ""

    def _format_tree_structure(self, node: Dict[str, Any], show_values: bool = False, indent: int = 0) -> List[str]:
        try:
            lines = []
            var = node.get("var", {})
            type_ = var.get("type", "")
            name = var.get("name", "")
            value = var.get("value", "")
            
            if show_values:
                lines.append("   " * indent + f"- \"type\": \"{type_}\", \"name\": \"{name}\", \"value\": \"{value}\"")
            else:
                lines.append("   " * indent + f"- \"type\": \"{type_}\", \"name\": \"{name}\"")
            
            for child in node.get("children", []):
                child_lines = self._format_tree_structure(child, show_values, indent + 1)
                lines.extend(child_lines)
                
            return lines
        except Exception as e:
            self.logger.error(f"Error in _format_tree_structure: {str(e)}")
            return []