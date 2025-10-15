import json
import os
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from utils.io import IOExtractor
from utils.llm_client import OpenAIClient
from utils.logger import get_logger

class DebugEngine:

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = get_logger("debug_engine")
        self.client = OpenAIClient()
        self.io_extractor = IOExtractor()
        
        self.model = config.get("model", "gpt-4o")
        
    def start_debugging(self, debug_data: Dict[str, Any], debug_state=None, selected=None):
        """ Entry of Debugging Engine """
        try:
            self.debug_data = debug_data
            self.selected_override = selected  # Store the selected parameter
            
            if debug_state is None:
                self.call_id = debug_data["start_info"]["test_trace"]
                self.method_name = debug_data["start_info"]["test_unit"]
                self.start_line = debug_data["code_info"][self.method_name]["start_line"]
                self.end_line = debug_data["code_info"][self.method_name]["end_line"]
                self.code = debug_data["code_info"][self.method_name]["whole"]
                self.stack = self.method_name
                self.context = "test task summary (groundtruth):\n" + debug_data["start_info"]["test_task"] + "\nreport from test unit:\n" + debug_data["start_info"]["test_failure"]

                current_state = [1, 1, 1, 1]
                messages, result =  self._execute_partition()
                self.save_state(current_state, messages, result)

            else:
                current_state = debug_state
                reliable_data = self.load_state(current_state)
                self.call_id = reliable_data["result"]["call_id"]
                self.method_name = reliable_data["result"]["method_name"]
                self.start_line = reliable_data["result"]["start_line"]
                self.end_line = reliable_data["result"]["end_line"]
                self.code = reliable_data["result"]["code"]
                self.stack = reliable_data["result"]["stack"]
                self.context = reliable_data["result"]["context"]

            result = self._debug_main_loop(current_state)
            return result
            
        except Exception as e:
            self.logger.error(f"Debugging Engine failure: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def _debug_main_loop(self, debug_state):
        try:
            current_state = debug_state
            iteration_count = 0
            while True:
                iteration_count += 1
                self.logger.info(f"Debugging Iteration {iteration_count}")
                
                new_state = current_state.copy()
                previous_data = {}

                if current_state[2] == 1 and current_state[3] == 1:
                    temp_state = current_state
                    temp_data = self.load_state(temp_state)
                    previous_data["list"] = temp_data["result"]["list"]["list"]

                    if current_state[1] > 1 and len(previous_data["list"]) == 1:
                        # impartible
                        self.remove_state(current_state)
                        new_state[1] -= 1
                        new_state[2] = 2
                        new_state[3] = 1

                        temp_state[1] -= 1
                        temp_state[3] = 2
                        temp_data = self.load_state(temp_state)
                        previous_data["selected"] = temp_data["result"]["selected"]

                        temp_state[3] = 5
                        temp_data = self.load_state(temp_state)
                        previous_data["record"] = self.extract_call(temp_data["result"]["selected"])
                    else:
                        # selection after partition
                        new_state[3] = 2
                        
                        previous_data["blocks"] = temp_data["result"]["list"]["blocks"]

                elif current_state[2] == 1 and current_state[3] == 2:
                    # abstraction after selection
                    new_state[3] = 3

                    temp_state = current_state
                    temp_data = self.load_state(temp_state)
                    previous_data["selected"] = temp_data["result"]["selected"]

                elif current_state[2] == 1 and current_state[3] == 3:
                    # extraction after abstraction
                    new_state[3] = 4

                    temp_state = current_state
                    temp_state[3] = 2
                    temp_data = self.load_state(temp_state)
                    previous_data["selected"] = temp_data["result"]["selected"]

                    temp_state[3] = 1
                    temp_data = self.load_state(temp_state)
                    previous_data["list"] = temp_data["result"]["list"]["list"]

                elif current_state[2] == 1 and current_state[3] == 4:
                    # combination after extraction
                    new_state[3] = 5

                    temp_state = current_state
                    temp_data = self.load_state(temp_state)
                    previous_data["expectation"] = temp_data["result"]["expectation"]["expectations_str"]

                    temp_state[3] = 3
                    temp_data = self.load_state(temp_state)
                    previous_data["presentation"] = temp_data["result"]["presentation"]["presentation_str"]
                    
                    temp_state[3] = 2
                    temp_data = self.load_state(temp_state)
                    previous_data["block"] = temp_data["result"]["selected"]

                    previous_data["input"], previous_data["output"], previous_data["invalue"], previous_data["outvalue"], previous_data["selected"] = self.extract_io()

                elif current_state[2] == 1 and current_state[3] == 5:
                    # prediction after combination
                    new_state[3] = 6

                    temp_state = current_state
                    temp_data = self.load_state(temp_state)
                    previous_data["specification"] = temp_data["result"]["specification"]["specification_str"]
                    previous_data["invalue"] = temp_data["result"]["invalue"]
                    previous_data["messages"] = temp_data["messages"]

                elif current_state[2] == 1 and current_state[3] == 6:
                    # comparison after prediction
                    new_state[3] = 7

                    temp_state = current_state
                    temp_data = self.load_state(temp_state)
                    previous_data["oracle"] = temp_data["result"]["oracle"]
                    previous_data["messages"] = temp_data["messages"]

                    temp_state[3] = 5
                    temp_data = self.load_state(temp_state)
                    previous_data["outvalue"] = temp_data["result"]["outvalue"]
                    
                    temp_state[3] = 1
                    temp_data = self.load_state(temp_state)
                    previous_data["list"] = temp_data["result"]["list"]["list"]

                elif current_state[2] == 1 and current_state[3] == 7:
                    # if consistent: rejection
                    # if inconsistent & minimum: localization after comparison
                    # if inconsistent & !minimum: partition after comparison
                    temp_state = current_state
                    temp_data = self.load_state(temp_state)

                    if temp_data["result"]["match"]["consistent"] == 1:
                        while (current_state[3] != 1):
                            self.remove_state(current_state)
                            current_state[3] -= 1

                        current_data = self.load_state(current_state)
                        current_data["result"]["contenxt"] = temp_data["result"]["context"]
                        self.save_state(current_state, current_data["messages"], current_data["result"])
                        continue


                    flag = temp_data["result"]["minimum"] == 1 or self.start_line == self.end_line or current_state[1] >= 2
                    # result = self.wait_for_step("check details")
                    # if result is not None and result.strip().isdigit():
                    #     flag = int(result) == 1
                    
                    if flag:
                        new_state[2] = 2
                        new_state[3] = 1
                        
                        temp_state[3] = 2
                        temp_data = self.load_state(temp_state)
                        previous_data["selected"] = temp_data["result"]["selected"]

                        temp_state[3] = 5
                        temp_data = self.load_state(temp_state)
                        previous_data["record"] = self.extract_call(temp_data["result"]["selected"])
                        
                    else:
                        new_state[1] += 1
                        new_state[3] = 1
                    
                elif current_state[2] == 2 and current_state[3] == 1:
                    # partition after localization step-in
                    new_state[0] += 1
                    new_state[1] = 1
                    new_state[2] = 1
                    new_state[3] = 1

                if new_state[2] == 1 and new_state[3] == 1:
                    messages, result =  self._execute_partition()
                elif new_state[2] == 1 and new_state[3] == 2:
                    messages, result = self._execute_selection(previous_data)
                elif new_state[2] == 1 and new_state[3] == 3:
                    messages, result = self._execute_abstraction(previous_data)
                elif new_state[2] == 1 and new_state[3] == 4:
                    messages, result = self._execute_extraction(previous_data)
                elif new_state[2] == 1 and new_state[3] == 5:
                    messages, result = self._execute_combination(previous_data)
                elif new_state[2] == 1 and new_state[3] == 6:
                    messages, result = self._execute_prediction(previous_data)
                elif new_state[2] == 1 and new_state[3] == 7:
                    messages, result = self._execute_comparison(previous_data)
                elif new_state[2] == 2 and new_state[3] == 1:
                    messages, result = self._execute_localization(previous_data)
                    if result["location"]["fault"] == 1:
                        self.save_state(new_state, messages, result)
                        return {"state": "root cause found."}
                
                self.save_state(new_state, messages, result)
                # self.wait_for_step()
                current_state = new_state
                if self.selected_override is not None:
                    return {"status": "success", "message": "Selected parameter overridden."}

        except Exception as e:
            self.logger.error(f"Main Loop failure: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def _execute_partition(self):
        params = {}
        params["code"] = self.code
        params["context"] = self.context
        params["test"] = self.debug_data["start_info"]["test_task"] + "\n" + self.debug_data["start_info"]["test_failure"]
        params["stack"] = self.stack

        self.logger.info("Agent Partition started.")
        try:
            with open("prompt/agent_partition.txt", "r", encoding="utf-8") as f:
                prompt_partition = f.read()
            
            messages = []
            formatted_prompt = prompt_partition.format(
                code=params["code"],
                context=params["context"],
                test=params["test"],
                stack=params["stack"]
            )
            messages.append({"role": "user", "content": formatted_prompt})

            for attempt in range(1):
                try:
                    response = self.client.getResponse(
                        model=self.model,
                        messages=messages
                    )
                    ai_reply = response.choices[0].message.content
                    
                    partition_list = self._parse_partition(ai_reply)
                    if partition_list is not None:
                        messages.append({"role": "assistant", "content": ai_reply})
                        result = {
                            "list": partition_list,
                            "call_id": self.call_id,
                            "method_name": self.method_name,
                            "start_line": self.start_line,
                            "end_line": self.end_line,
                            "code": self.code,
                            "stack": self.stack,
                            "context": self.context
                        }

                        return messages, result
                    
                except Exception as e:
                    self.logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt == 4:
                        raise e
        except Exception as e:
            self.logger.warning(f"Agent Partition failed: {str(e)}")
            return [], {"error": f"Agent Partition failed: {str(e)}"}
    
    def _execute_selection(self, previous_data):
        params = {}
        params["code"] = self.code
        params["context"] = self.context
        params["list"] = '\n'.join(previous_data["list"])

        self.logger.info("Agent Selection started.")
        try:
            with open("prompt/agent_selection.txt", "r", encoding="utf-8") as f:
                prompt_selection = f.read()

            messages = []
            formatted_prompt = prompt_selection.format(
                code=params["code"],
                context=params["context"],
                list=params["list"]
            )
            messages.append({"role": "user", "content": formatted_prompt})

            for attempt in range(1):
                try:
                    response = self.client.getResponse(
                        model=self.model,
                        messages=messages
                    )
                    ai_reply = response.choices[0].message.content
                    selected = self._parse_selection(ai_reply)
                    if selected is not None:
                        self.start_line = previous_data["blocks"][selected["id"]]["start_line"]
                        self.end_line = previous_data["blocks"][selected["id"]]["end_line"]
                        self.code = self.cut_code_snippet(self.code, self.start_line, self.end_line)

                        messages.append({"role": "assistant", "content": ai_reply})
                        result = {
                            "selected": previous_data["list"][selected["id"]],
                            "call_id": self.call_id,
                            "method_name": self.method_name,
                            "start_line": self.start_line,
                            "end_line": self.end_line,
                            "code": self.code,
                            "stack": self.stack,
                            "context": self.context
                        }

                        return messages, result
                    
                except Exception as e:
                    self.logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt == 4:
                        raise e
        except Exception as e:
            self.logger.warning(f"Agent Selection failed: {str(e)}")
            return [], {"error": f"Agent Selection failed: {str(e)}"}

    def _execute_abstraction(self, previous_data):
        params = {}
        params["code"] = self.code
        params["context"] = self.context
        params["selected"] = previous_data["selected"]

        self.logger.info("Agent Abstraction started.")
        try:
            with open("prompt/agent_abstraction.txt", "r", encoding="utf-8") as f:
                prompt_abstraction = f.read()

            messages = []
            formatted_prompt = prompt_abstraction.format(
                code=params["code"],
                context=params["context"],
                selected=params["selected"]
            )
            messages.append({"role": "user", "content": formatted_prompt})

            for attempt in range(1):
                try:
                    response = self.client.getResponse(
                        model=self.model,
                        messages=messages
                    )
                    ai_reply = response.choices[0].message.content
                    
                    presentation = self._parse_abstraction(ai_reply)
                    if presentation is not None:
                        messages.append({"role": "assistant", "content": ai_reply})
                        result = {
                            "presentation": presentation,
                            "call_id": self.call_id,
                            "method_name": self.method_name,
                            "start_line": self.start_line,
                            "end_line": self.end_line,
                            "code": self.code,
                            "stack": self.stack,
                            "context": self.context
                        }

                        return messages, result
                    
                except Exception as e:
                    self.logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt == 4:
                        raise e
        except Exception as e:
            self.logger.warning(f"Agent Abstraction failed: {str(e)}")
            return [], {"error": f"Agent Abstraction failed: {str(e)}"}

    def _execute_extraction(self, previous_data):
        params = {}
        params["selected"] = previous_data["selected"]
        params["list"] = '\n'.join(previous_data["list"])
        params["context"] = self.context

        self.logger.info("Agent Extraction started.")
        try:
            with open("prompt/agent_extraction.txt", "r", encoding="utf-8") as f:
                prompt_extraction = f.read()

            messages = []
            formatted_prompt = prompt_extraction.format(
                selected=params["selected"],
                list=params["list"],
                context=params["context"]
            )
            messages.append({"role": "user", "content": formatted_prompt})

            for attempt in range(1):
                try:
                    response = self.client.getResponse(
                        model=self.model,
                        messages=messages
                    )
                    ai_reply = response.choices[0].message.content
                    
                    expectation = self._parse_extraction(ai_reply)
                    if expectation is not None:
                        messages.append({"role": "assistant", "content": ai_reply})
                        result = {
                            "expectation": expectation,
                            "call_id": self.call_id,
                            "method_name": self.method_name,
                            "start_line": self.start_line,
                            "end_line": self.end_line,
                            "code": self.code,
                            "stack": self.stack,
                            "context": self.context
                        }

                        return messages, result
                    
                except Exception as e:
                    self.logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt == 4:
                        raise e
        except Exception as e:
            self.logger.warning(f"Agent Extraction failed: {str(e)}")
            return [], {"error": f"Agent Extraction failed: {str(e)}"}

    def _execute_combination(self, previous_data):
        params = {}
        params["code"] = self.code
        params["block"] = previous_data["block"]
        params["presentation"] = previous_data["presentation"]
        params["expectation"] = previous_data["expectation"]
        params["input"] = previous_data["input"]
        params["output"] = previous_data["output"]
        params["invalue"] = previous_data["invalue"]
        params["outvalue"] = previous_data["outvalue"]

        self.logger.info("Agent Combination started.")
        try:
            with open("prompt/agent_combination.txt", "r", encoding="utf-8") as f:
                prompt_combination = f.read()

            messages = []
            formatted_prompt = prompt_combination.format(
                code=params["code"],
                selected=params["block"],
                presentation=params["presentation"],
                expectation=params["expectation"],
                input=params["input"],
                output=params["output"]
            )
            messages.append({"role": "user", "content": formatted_prompt})

            for attempt in range(1):
                try:
                    response = self.client.getResponse(
                        model=self.model,
                        messages=messages
                    )
                    ai_reply = response.choices[0].message.content

                    specification = self._parse_combination(ai_reply)
                    if specification is not None:
                        messages.append({"role": "assistant", "content": ai_reply})
                        result = {
                            "specification": specification,
                            "call_id": self.call_id,
                            "method_name": self.method_name,
                            "start_line": self.start_line,
                            "end_line": self.end_line,
                            "code": self.code,
                            "stack": self.stack,
                            "context": self.context,
                            "invalue": params["invalue"],
                            "outvalue": params["outvalue"],
                            "selected": previous_data["selected"]
                        }

                        return messages, result
                    
                except Exception as e:
                    self.logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt == 4:
                        raise e
        except Exception as e:
            self.logger.warning(f"Agent Combination failed: {str(e)}")
            return [], {"error": f"Agent Combination failed: {str(e)}"}

    def _execute_prediction(self, previous_data):
        params = {}
        params["specification"] = previous_data["specification"]
        params["invalue"] = previous_data["invalue"]
        params["context"] = self.context

        self.logger.info("Agent Prediction started.")
        try:
            with open("prompt/agent_prediction.txt", "r", encoding="utf-8") as f:
                prompt_prediction = f.read()

            messages = previous_data["messages"]
            formatted_prompt = prompt_prediction.format(
                specification=params["specification"],
                invalue=params["invalue"],
                context=params["context"]
            )
            messages.append({"role": "user", "content": formatted_prompt})

            for attempt in range(1):
                try:
                    response = self.client.getResponse(
                        model=self.model,
                        messages=messages
                    )
                    ai_reply = response.choices[0].message.content

                    oracle = self._parse_prediction(ai_reply)
                    if oracle is not None:
                        messages.append({"role": "assistant", "content": ai_reply})
                        result = {
                            "oracle": oracle,
                            "call_id": self.call_id,
                            "method_name": self.method_name,
                            "start_line": self.start_line,
                            "end_line": self.end_line,
                            "code": self.code,
                            "stack": self.stack,
                            "context": self.context
                        }

                        return messages, result
                    
                except Exception as e:
                    self.logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt == 4:
                        raise e
        except Exception as e:
            self.logger.warning(f"Agent Prediction failed: {str(e)}")
            return [], {"error": f"Agent Prediction failed: {str(e)}"}

    def _execute_comparison(self, previous_data):
        params = {}
        params["oracle"] = previous_data["oracle"]
        params["outvalue"] = previous_data["outvalue"]

        self.logger.info("Agent Comparison started.")
        try:
            with open("prompt/agent_comparison.txt", "r", encoding="utf-8") as f:
                prompt_comparison = f.read()

            messages = previous_data["messages"]
            formatted_prompt = prompt_comparison.format(
                oracle=params["oracle"]["prediction_str"],
                outvalue=params["outvalue"]
            )
            messages.append({"role": "user", "content": formatted_prompt})

            for attempt in range(1):
                try:
                    response = self.client.getResponse(
                        model=self.model,
                        messages=messages
                    )
                    ai_reply = response.choices[0].message.content

                    match = self._parse_comparison(ai_reply, params["oracle"]["oracle"])
                    if match is not None:
                        self.context = self.context + f"\n\nanalysis from {self.method_name}[{self.start_line}:{self.end_line}]:\n" + match["summary"]

                        messages.append({"role": "assistant", "content": ai_reply})
                        result = {
                            "match": match,
                            "call_id": self.call_id,
                            "method_name": self.method_name,
                            "start_line": self.start_line,
                            "end_line": self.end_line,
                            "code": self.code,
                            "stack": self.stack,
                            "context": self.context,
                            "minimum": len(previous_data["list"])
                        }

                        return messages, result
                    
                except Exception as e:
                    self.logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt == 4:
                        raise e
        except Exception as e:
            self.logger.warning(f"Agent Comparison failed: {str(e)}")
            return [], {"error": f"Agent Comparison failed: {str(e)}"}

    def _execute_localization(self, previous_data):
        params = {}
        params["code"] = self.debug_data["code_info"][self.method_name]["whole"]
        params["context"] = self.context
        params["selected"] = previous_data["selected"]
        params["record"] = previous_data["record"]

        self.logger.info("Agent Localization started.")
        try:
            with open("prompt/agent_localization.txt", "r", encoding="utf-8") as f:
                prompt_localization = f.read()

            messages = []
            formatted_prompt = prompt_localization.format(
                code=params["code"],
                context=params["context"],
                selected=params["selected"],
                record=params["record"]
            )
            messages.append({"role": "user", "content": formatted_prompt})

            for attempt in range(1):
                try:
                    response = self.client.getResponse(
                        model=self.model,
                        messages=messages
                    )
                    ai_reply = response.choices[0].message.content

                    location = self._parse_localization(ai_reply, params["record"])
                    if location is not None:
                        if location["fault"] != 1:
                            self.call_id = location["details"]
                            self.method_name = self.debug_data["call_info"][self.call_id]["method_name"]
                            self.start_line = self.debug_data["code_info"][self.method_name]["start_line"]
                            self.end_line = self.debug_data["code_info"][self.method_name]["end_line"]
                            self.code = self.debug_data["code_info"][self.method_name]["whole"]
                            self.stack = self.stack + "\n" + self.method_name

                        messages.append({"role": "assistant", "content": ai_reply})
                        result = {
                            "location": location,
                            "call_id": self.call_id,
                            "method_name": self.method_name,
                            "start_line": self.start_line,
                            "end_line": self.end_line,
                            "code": self.code,
                            "stack": self.stack,
                            "context": self.context
                        }

                        return messages, result
                    
                except Exception as e:
                    self.logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt == 4:
                        raise e
        except Exception as e:
            self.logger.warning(f"Agent Localization failed: {str(e)}")
            return [], {"error": f"Agent Localization failed: {str(e)}"}

    def _parse_partition(self, ai_reply):
        # parse the partition list from the AI response
        # if illegal, return None
        try:
            if "<format>" in ai_reply and "</format>" in ai_reply:
                format_start = ai_reply.find("<format>") + len("<format>")
                format_end = ai_reply.find("</format>")
                format_content = ai_reply[format_start:format_end].strip()
            else:
                format_content = ai_reply.strip()
            
            lines = format_content.split('\n')
            start_line = None
            end_line = None
            description = None
            blocks = []
            list = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if '"start_line":' in line:
                    start_line = int(line.split(':')[1].strip().rstrip(','))
                
                elif '"end_line":' in line:
                    end_line = int(line.split(':')[1].strip().rstrip(','))
                
                elif '"description":' in line:
                    desc_start = line.find('"description":') + len('"description":')
                    description = line[desc_start:].strip().strip('"').rstrip(',')
                
                elif '"line":' in line and '"comment":' in line:
                    line_part = line.split('"line":')[1].split(',')[0].strip()
                    comment_part = line.split('"comment":')[1].strip().strip('"')
                    
                    block_line = int(line_part)
                    block_comment = comment_part
                    
                    blocks.append({
                        "id": len(blocks),
                        "end_line": block_line,
                        "comment": block_comment
                    })
                    if len(blocks) == 1:
                        blocks[0]["start_line"] = start_line
                    else:
                        blocks[-1]["start_line"] = blocks[-2]["end_line"] + 1
                    
                    block_desc = f"- ID: {blocks[-1]['id']}, Line {blocks[-1]['start_line']}-{blocks[-1]['end_line']}: {block_comment}"
                    list.append(block_desc)

            if start_line is None or end_line is None or description is None or not blocks:
                self.logger.warning("Missing required fields in partition response")
                return None
            
            self.logger.info(f"Parsed partition with {len(blocks)} blocks from line {start_line} to {end_line}")
            return {
                "start_line": start_line,
                "end_line": end_line,
                "description": description,
                "blocks": blocks,
                "list": list
            }
            
        except Exception as e:
            self.logger.warning(f"failed to parse partition response: {str(e)}")
            return None

    def _parse_selection(self, ai_reply):
        # parse the selected one from the AI response
        # if illegal, return None
        try:
            if "<format>" in ai_reply and "</format>" in ai_reply:
                format_start = ai_reply.find("<format>") + len("<format>")
                format_end = ai_reply.find("</format>")
                format_content = ai_reply[format_start:format_end].strip()
            else:
                format_content = ai_reply.strip()
            
            lines = format_content.split('\n')
            analysis = None
            selected_id = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if '"analysis":' in line:
                    analysis_start = line.find('"analysis":') + len('"analysis":')
                    analysis = line[analysis_start:].strip().strip('"').rstrip(',')
                
                elif '"id":' in line:
                    id_part = line.split(':')[1].strip().rstrip(',')
                    selected_id = int(id_part)
            
            if analysis is None or selected_id is None:
                self.logger.warning("Missing required fields in selection response")
                return None
            
            self.logger.info(f"Parsed selection: selected block ID {selected_id}")

            # 检查selected_override参数，若不为-1，则替换selected_id
            if hasattr(self, 'selected_override') and self.selected_override is not None and self.selected_override != -1:
                selected_id = self.selected_override
                analysis = f"Override by user selection: {selected_id}"
                self.logger.info(f"Using selected override: {selected_id}")
            
            return {
                "analysis": analysis,
                "id": selected_id
            }
            
        except Exception as e:
            self.logger.warning(f"failed to parse selection response: {str(e)}")
            return None

    def _parse_abstraction(self, ai_reply):
        # parse the abstracted presentation from the AI response
        # if illegal, return None
        try:
            if "<format>" in ai_reply and "</format>" in ai_reply:
                format_start = ai_reply.find("<format>") + len("<format>")
                format_end = ai_reply.find("</format>")
                format_content = ai_reply[format_start:format_end].strip()
            else:
                format_content = ai_reply.strip()
            
            lines = format_content.split('\n')
            signature = None
            intent = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if '"signature":' in line:
                    signature_start = line.find('"signature":') + len('"signature":')
                    signature = line[signature_start:].strip().strip('"').rstrip(',')
                
                elif '"intent":' in line:
                    intent_start = line.find('"intent":') + len('"intent":')
                    intent = line[intent_start:].strip().strip('"').rstrip(',')
                
                presentation_str = f"signature: \"{signature}\",\nintent: \"{intent}\""
            
            if signature is None or intent is None:
                self.logger.warning("Missing required fields in abstraction response")
                return None
            
            self.logger.info(f"Parsed abstraction: signature='{signature}', intent='{intent}'")
            return {
                "signature": signature,
                "intent": intent,
                "presentation_str": presentation_str
            }
            
        except Exception as e:
            self.logger.warning(f"failed to parse abstraction response: {str(e)}")
            return None

    def _parse_extraction(self, ai_reply):
        # parse the historical expectation from the AI response
        # if illegal, return None
        try:
            if "<format>" in ai_reply and "</format>" in ai_reply:
                format_start = ai_reply.find("<format>") + len("<format>")
                format_end = ai_reply.find("</format>")
                format_content = ai_reply[format_start:format_end].strip()
            else:
                format_content = ai_reply.strip()
            
            lines = format_content.split('\n')
            expectations = []
            expectations_str = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if '"object":' in line and '"stage":' in line and '"expect":' in line:
                    # Parse object - find quoted string carefully
                    object_start = line.find('"object":') + len('"object":')
                    object_start = line.find('"', object_start) + 1  # Find opening quote
                    object_end = line.find('", "stage":', object_start)  # Find closing quote before stage
                    object_part = line[object_start:object_end]
                    
                    # Parse stage - find quoted string carefully
                    stage_start = line.find('"stage":') + len('"stage":')
                    stage_start = line.find('"', stage_start) + 1  # Find opening quote
                    stage_end = line.find('", "expect":', stage_start)  # Find closing quote before expect
                    stage_part = line[stage_start:stage_end]
                    
                    # Parse expect - find quoted string carefully
                    expect_start = line.find('"expect":') + len('"expect":')
                    expect_start = line.find('"', expect_start) + 1  # Find opening quote
                    # Find the last quote in the line (end of expect value)
                    expect_end = line.rfind('"')
                    expect_part = line[expect_start:expect_end]
                    
                    expectations.append({
                        "object": object_part,
                        "stage": stage_part,
                        "expect": expect_part
                    })
                    
                    expectation_str = f"- \"object\": \"{object_part}\", \"stage\": \"{stage_part}\", \"expect\": \"{expect_part}\""
                    expectations_str.append(expectation_str)
            
            # if not expectations:
            #     self.logger.warning("No expectations found in extraction response")
            #     return None
            
            result = {
                "expectations": expectations,
                "expectations_str": expectations_str,
            }
            
            self.logger.info(f"Parsed extraction with {len(expectations)} expectations")
            return result
            
        except Exception as e:
            self.logger.warning(f"failed to parse extraction response: {str(e)}")
            return None

    def _parse_combination(self, ai_reply):
        # parse the model-executable Specification from the AI response
        # if illegal, return None
        try:
            if "<format>" in ai_reply and "</format>" in ai_reply:
                format_start = ai_reply.find("<format>") + len("<format>")
                format_end = ai_reply.find("</format>")
                format_content = ai_reply[format_start:format_end].strip()
            else:
                format_content = ai_reply.strip()
            
            lines = format_content.split('\n')
            input_vars = []
            output_vars = []
            operational_semantics = []
            current_section = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if '"input":' in line:
                    current_section = "input"
                elif '"output":' in line:
                    current_section = "output"
                elif '"operational_semantics":' in line:
                    current_section = "operational_semantics"
                
                elif current_section == "input" and '"name":' in line and '"detail":' in line:
                    # Parse name - find quoted string carefully
                    name_start = line.find('"name":') + len('"name":')
                    name_start = line.find('"', name_start) + 1  # Find opening quote
                    name_end = line.find('", "detail":', name_start)  # Find closing quote before detail
                    name_part = line[name_start:name_end]
                    
                    # Parse detail - find quoted string carefully
                    detail_start = line.find('"detail":') + len('"detail":')
                    detail_start = line.find('"', detail_start) + 1  # Find opening quote
                    detail_end = line.rfind('"')  # Find the last quote in the line
                    detail_part = line[detail_start:detail_end]
                    
                    input_vars.append({
                        "name": name_part,
                        "detail": detail_part
                    })
                
                elif current_section == "output" and '"name":' in line and '"detail":' in line:
                    # Parse name - find quoted string carefully
                    name_start = line.find('"name":') + len('"name":')
                    name_start = line.find('"', name_start) + 1  # Find opening quote
                    name_end = line.find('", "detail":', name_start)  # Find closing quote before detail
                    name_part = line[name_start:name_end]
                    
                    # Parse detail - find quoted string carefully
                    detail_start = line.find('"detail":') + len('"detail":')
                    detail_start = line.find('"', detail_start) + 1  # Find opening quote
                    detail_end = line.rfind('"')  # Find the last quote in the line
                    detail_part = line[detail_start:detail_end]
                    
                    output_vars.append({
                        "name": name_part,
                        "detail": detail_part
                    })
                
                elif current_section == "operational_semantics" and line.startswith('- "') and line.endswith('"'):
                    semantic_item = line[3:-1]  # 去掉 '- "' 和 '"'
                    operational_semantics.append(semantic_item)
            
            if not input_vars and not output_vars and not operational_semantics:
                self.logger.warning("Missing required fields in combination response")
                return None

            specification_str = "\"input\":\n"
            for input_var in input_vars:
                specification_str = specification_str + f"- \"name\": \"{input_var['name']}\", \"detail\": \"{input_var['detail']}\"\n"
            specification_str = specification_str + "\"output\":\n"
            for output_var in output_vars:
                specification_str = specification_str + f"- \"name\": \"{output_var['name']}\", \"detail\": \"{output_var['detail']}\"\n"
            specification_str = specification_str + "\"operational_semantics\":\n"
            for semantic in operational_semantics:
                specification_str = specification_str + f"- \"{semantic}\"\n"

            self.logger.info(f"Parsed combination with {len(input_vars)} inputs, {len(output_vars)} outputs, {len(operational_semantics)} semantics")
            return {
                "input": input_vars,
                "output": output_vars,
                "operational_semantics": operational_semantics,
                "specification_str": specification_str
            }
            
        except Exception as e:
            self.logger.warning(f"failed to parse combination response: {str(e)}")
            return None

    def _parse_prediction(self, ai_reply):
        # parse the oracle from the AI response
        # if illegal, return None
        try:
            if "<format>" in ai_reply and "</format>" in ai_reply:
                format_start = ai_reply.find("<format>") + len("<format>")
                format_end = ai_reply.find("</format>")
                format_content = ai_reply[format_start:format_end].strip()
            else:
                format_content = ai_reply.strip()
            
            lines = format_content.split('\n')
            oracle_items = []
            current_section = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if '"oracle":' in line:
                    current_section = "oracle"
                
                elif current_section == "oracle" and '"name":' in line and '"analysis":' in line and '"expected":' in line:
                    # Parse name - find quoted string carefully
                    name_start = line.find('"name":') + len('"name":')
                    name_start = line.find('"', name_start) + 1  # Find opening quote
                    name_end = line.find('", "analysis":', name_start)  # Find closing quote before analysis
                    name_part = line[name_start:name_end]
                    
                    # Parse analysis - find quoted string carefully
                    analysis_start = line.find('"analysis":') + len('"analysis":')
                    analysis_start = line.find('"', analysis_start) + 1  # Find opening quote
                    analysis_end = line.find('", "expected":', analysis_start)  # Find closing quote before expected
                    analysis_part = line[analysis_start:analysis_end]
                    
                    # Parse expected - find quoted string carefully
                    expected_start = line.find('"expected":') + len('"expected":')
                    expected_start = line.find('"', expected_start) + 1  # Find opening quote
                    expected_end = line.rfind('"')  # Find the last quote in the line
                    expected_part = line[expected_start:expected_end]
                    
                    oracle_items.append({
                        "name": name_part,
                        "analysis": analysis_part,
                        "expected": expected_part
                    })
            
            if not oracle_items:
                self.logger.warning("No oracle items found in prediction response")
                return None
            
            prediction_str = "\"oracle\":\n"
            for oracle in oracle_items:
                prediction_str = prediction_str + f"- \"name\": \"{oracle['name']}\", \"analysis\": \"{oracle['analysis']}\", \"expected\": \"{oracle['expected']}\"\n"

            self.logger.info(f"Parsed prediction with {len(oracle_items)} oracle items")
            return {
                "oracle": oracle_items,
                "prediction_str": prediction_str
            }
            
        except Exception as e:
            self.logger.warning(f"failed to parse prediction response: {str(e)}")
            return None

    def _parse_comparison(self, ai_reply, oracle):
        # parse the match & summary from the AI response
        # if illegal, return None
        try:
            if "<format>" in ai_reply and "</format>" in ai_reply:
                format_start = ai_reply.find("<format>") + len("<format>")
                format_end = ai_reply.find("</format>")
                format_content = ai_reply[format_start:format_end].strip()
            else:
                format_content = ai_reply.strip()
            
            lines = format_content.split('\n')
            match_items = []
            summary = None
            current_section = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if '"match":' in line:
                    current_section = "match"
                elif '"summary":' in line:
                    summary_start = line.find('"summary":') + len('"summary":')
                    summary = line[summary_start:].strip().strip('"').rstrip(',')
                    current_section = "summary"
                
                elif current_section == "match" and '"name":' in line and '"actual":' in line and '"reason":' in line and '"consistent":' in line:
                    # Extract name
                    name_start = line.find('"name":') + len('"name":')
                    name_end = line.find(',', name_start)
                    name_part = line[name_start:name_end].strip().strip('"')
                    
                    # Extract actual - need to handle quoted strings with commas carefully
                    actual_start = line.find('"actual":') + len('"actual":')
                    actual_start = line.find('"', actual_start) + 1  # Find opening quote
                    actual_end = line.find('", "reason":', actual_start)  # Find closing quote before reason
                    actual_part = line[actual_start:actual_end]
                    
                    # Extract reason - similar careful handling
                    reason_start = line.find('"reason":') + len('"reason":')
                    reason_start = line.find('"', reason_start) + 1  # Find opening quote
                    reason_end = line.find('", "consistent":', reason_start)  # Find closing quote before consistent
                    reason_part = line[reason_start:reason_end]
                    
                    # Extract consistent value
                    consistent_start = line.find('"consistent":') + len('"consistent":')
                    consistent_part = line[consistent_start:].strip().rstrip(',')
                    consistent_value = int(consistent_part)
                    
                    match_items.append({
                        "name": name_part,
                        "actual": actual_part,
                        "reason": reason_part,
                        "consistent": consistent_value
                    })
            
            if not match_items or summary is None:
                self.logger.warning("Missing required fields in comparison response")
                return None
            
            for item in match_items:
                if item.get("consistent", 0) == 0:
                    item_oracle = None
                    for o in oracle:
                        if o.get("name", "No name") == item["name"]:
                            item_oracle = o
                            break
                    if item_oracle is None:
                        continue

                    if item_oracle.get("expected", "No value") == "No value":
                        continue
                    if item["value"] == item_oracle["expected"]:
                        item["consistent"] = 1
                        item["reason"] = f"Actual value matches expected"
                    if item["type"] in ["float"]:
                        try:
                            actual_float = float(item["actual"])
                            expected_float = float(item_oracle["expected"])
                            if abs(actual_float - expected_float) < 1e-10:
                                item["consistent"] = 1
                                item["reason"] = f"Actual value approximately matches expected"
                        except ValueError:
                            pass
                    if item["type"] in ["list", "dict"]:
                        try:
                            actual_json = json.loads(item["actual"])
                            expected_json = json.loads(item_oracle["expected"])
                            if actual_json == expected_json:
                                item["consistent"] = 1
                                item["reason"] = f"Actual value structurally matches expected"
                        except json.JSONDecodeError:
                            pass

            consistent_count = sum(1 for item in match_items if item["consistent"] == 1)
            overall_consistent = consistent_count / len(match_items) if match_items else 0.0
            
            self.logger.info(f"Parsed comparison with {len(match_items)} match items, overall consistent: {overall_consistent}")
            # self.wait_for_step()
            return {
                "match": match_items,
                "summary": summary,
                "consistent": overall_consistent
            }
            
        except Exception as e:
            self.logger.warning(f"failed to parse comparison response: {str(e)}")
            return None

    def _parse_localization(self, ai_reply, record):
        # parse the localization result from the AI response
        # if illegal, return None
        try:
            if "<format>" in ai_reply and "</format>" in ai_reply:
                format_start = ai_reply.find("<format>") + len("<format>")
                format_end = ai_reply.find("</format>")
                format_content = ai_reply[format_start:format_end].strip()
            else:
                format_content = ai_reply.strip()
            
            lines = format_content.split('\n')
            analysis = None
            fault = None
            details = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if '"analysis":' in line:
                    analysis_start = line.find('"analysis":') + len('"analysis":')
                    analysis = line[analysis_start:].strip().strip('"').rstrip(',')

                elif '"fault":' in line:
                    fault_part = line.split(':')[1].strip().rstrip(',')
                    fault = int(fault_part)
                
                elif '"details":' in line:
                    details_start = line.find('"details":') + len('"details":')
                    details_part = line[details_start:].strip().rstrip(',')
                    
                    try:
                        details = int(details_part)
                    except ValueError:
                        details = details_part.strip('"')
            
            if analysis is None or fault is None or details is None:
                self.logger.warning("Missing required fields in localization response")
                return None
            
            self.logger.info(f"Parsed localization: fault={fault}, details={details}")

            # 检查selected_override参数，根据其值修改fault和details
            if hasattr(self, 'selected_override') and self.selected_override is not None and self.selected_override != -1:
                if self.selected_override == 0:
                    # 若selected_override为0，则fault=1, details=0
                    fault = 1
                    details = 0
                    analysis = f"Override by user selection: fault=1 (root cause found), details=0"
                    self.logger.info(f"Override: fault=1 (root cause found), details=0")
                elif self.selected_override > 0:
                    # 若selected_override为正整数，则fault=0, details的值需要从record中提取
                    fault = 0
                    # 解析record字符串，提取call_id列表
                    record_lines = record.strip().split('\n') if record else []
                    record_items = []
                    for line in record_lines:
                        if ':' in line:
                            call_id_str, method_name = line.split(':', 1)
                            try:
                                call_id = int(call_id_str.strip())
                                record_items.append({"id": call_id, "method_name": method_name.strip()})
                            except ValueError:
                                continue
                    
                    # 根据selected_override作为下标提取details
                    if 0 < self.selected_override <= len(record_items):
                        details = record_items[self.selected_override - 1]["id"]  # 1-based index
                        method_name = record_items[self.selected_override - 1]["method_name"]
                        analysis = f"Override by user selection: fault=0 (step into), details={details} (call to {method_name})"
                        self.logger.info(f"Override: fault=0 (step into), details={details} (call_id from record index {self.selected_override})")
                    else:
                        self.logger.warning(f"selected_override {self.selected_override} is out of range for record (size: {len(record_items)})")
                        # 保持原始值不变

            return {
                "analysis": analysis,
                "fault": fault,
                "details": details
            }
            
        except Exception as e:
            self.logger.warning(f"failed to parse localization response: {str(e)}")
            return None

    def cut_code_snippet(self, code, start_line, end_line):
        # cut snippet from the code
        # code: code string with line-numbered
        # return the string part from start_line to end_line
        # for example:
        # input: code = "1   int main:\n2       c = a + b\n3       return c"
        # input: start_line=2, end_line=3
        # output: code = "2       c = a + b\n3       return c"
        try:
            if not code:
                return ""
            
            lines = code.split('\n')
            result_lines = []
            
            for line in lines:
                if not line.strip():
                    continue
                
                parts = line.split(None, 1)
                if not parts:
                    continue
                
                try:
                    line_num = int(parts[0])
                    if start_line <= line_num <= end_line:
                        result_lines.append(line)
                except ValueError:
                    continue
            
            return '\n'.join(result_lines)
            
        except Exception as e:
            self.logger.warning(f"Failed to cut code snippet: {str(e)}")
            return code

    def extract_io(self):
        # extract input output invalue outvalue
        # use utils/io.py
        io_data = {}
        input_data = ""
        output_data = ""
        invalue = ""
        outvalue = ""
        
        current_call = self.call_id
        start_line = self.start_line
        end_line = self.end_line

        try:
            trace_data = self.debug_data["original"]

            start_trace = self.debug_data["call_info"][current_call]["start"]
            end_trace = self.debug_data["call_info"][current_call]["end"]
        
            while (start_trace != self.debug_data["call_info"][current_call]["end"] and self.debug_data["original"][start_trace - 1]["line"] < start_line):
                start_trace = self.debug_data["original"][start_trace - 1]["son"]
            
            if self.debug_data["original"][start_trace - 1]["line"] < start_line:
                return "", "", "", "", {"execution_first": -1, "execution_last": -1}
            if self.debug_data["original"][start_trace - 1]["line"] > end_line:
                return "", "", "", "", {"execution_first": -1, "execution_last": -1}
            
            end_trace = start_trace
            while (self.debug_data["original"][end_trace - 1]["son"] != -1 and self.debug_data["original"][end_trace - 1]["line"] <= end_line):
                end_trace = self.debug_data["original"][end_trace - 1]["son"]
            if self.debug_data["original"][end_trace - 1]["line"] <= end_line:
                end_trace = self.debug_data["call_info"][current_call]["end"]
            else:
                end_trace = self.debug_data["original"][end_trace - 1]["sip"]
            
            # self.logger.debug(f"{self.debug_data['call_info'][current_call]['start']}, {self.debug_data['call_info'][current_call]['end']}")
            # self.logger.debug(f"{start_trace}, {end_trace}")

            io_data = self.io_extractor.extract_io_data(trace_data, current_call, start_trace, end_trace, self.debug_data["trace_fix"])

            block_read = io_data.get("block_read", [])
            block_write = io_data.get("block_write", [])
            
            if block_read:
                input_lines = []
                for item in block_read:
                    var = item[1]
                    input_lines.append(f"- {var.get('name', '')}: {var.get('type', '')}")
                input_data = "\n".join(input_lines)
            
            if block_write:
                output_lines = []
                for item in block_write:
                    var = item[1]
                    output_lines.append(f"- {var.get('name', '')}: {var.get('type', '')}")
                output_data = "\n".join(output_lines)
            
            invalue = io_data.get("invalue", "")
            outvalue = io_data.get("outvalue", "")
            
            selected = {}
            execution_range = io_data.get("execution_range", {})
            selected["execution_first"] = execution_range.get("first", -1)
            selected["execution_last"] = execution_range.get("last", -1)
                            
            self.logger.debug(f"Block {start_line}-{end_line}, {start_trace}-{end_trace}: extracted {len(block_read)} inputs, {len(block_write)} outputs")
            return input_data, output_data, invalue, outvalue, selected

        except Exception as e:
            self.logger.warning(f"Failed to extract IO data for block {start_line}-{end_line}: {str(e)}")
            return "", "", "", "", {"execution_first": -1, "execution_last": -1}

    def extract_call(self, selected):
        selected_block = selected
        execution_first = selected_block["execution_first"]
        execution_last = selected_block["execution_last"]
        
        record = []
        if execution_first != -1 and execution_last != -1:
            call_info = self.debug_data["call_info"]
            for call_id in call_info[self.call_id]["call_list"]:
                call_data = call_info[call_id]
                call_trace = call_data["call_trace"]
                call_start = call_data["start"]
                call_end = call_data["end"]

                if (call_trace != -1 and call_start != -1 and call_end != -1 and
                    execution_first <= call_start - 1 and execution_last >= call_start - 1):
                    method_name = call_data["method_name"]
                    record.append({
                        "id": call_id,
                        "method_name": method_name
                    })
                            
                    self.logger.debug(f"Added to record - call_id: {call_id}, method: {method_name}, "
                                    f"trace: {call_trace}, range: {call_start}-{call_end}")
                
        self.logger.info(f"Found {len(record)} calls in best block execution range")
        return '\n'.join([f"{item['id']}: {item['method_name']}" for item in record]) if record else "No calls found"

    def save_state(self, current_state, messages, result):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            state = {
                "timestamp": timestamp,
                "messages": messages,
                "result": result
            }
            state_str = "_".join(map(str, current_state))
            filename = f"result/{self.config['project_id']}_{self.config['bug_id']}/state_{state_str}.json"
            
            directory = os.path.dirname(filename)
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                self.logger.info(f"Created directory: {directory}")
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=4, ensure_ascii=False)
            self.logger.info(f"Debug state saved to {filename}")
        except Exception as e:
            self.logger.error(f"Failed to save debug state: {str(e)}")
    
    def load_state(self, current_state):
        try:
            state_str = "_".join(map(str, current_state))
            filename = f"result/{self.config['project_id']}_{self.config['bug_id']}/state_{state_str}.json"
            if not os.path.exists(filename):
                self.logger.warning(f"No saved state found at {filename}")
                return None
            with open(filename, 'r', encoding='utf-8') as f:
                state = json.load(f)
            self.logger.info(f"Debug state loaded from {filename}")
            return state
        except Exception as e:
            self.logger.error(f"Failed to load debug state: {str(e)}")
            return None

    def remove_state(self, current_state):
        try:
            state_str = "_".join(map(str, current_state))
            filename = f"result/{self.config['project_id']}_{self.config['bug_id']}/state_{state_str}.json"
            if not os.path.exists(filename):
                self.logger.warning(f"No saved state found at {filename}")
                return False
            os.remove(filename)
            self.logger.info(f"Debug state removed from {filename}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove debug state: {str(e)}")
            return False

    def wait_for_step(self, st = ""):
        ans = input(st)
        return ans