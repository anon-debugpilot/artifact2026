import sys
import subprocess
import json
import os
import time
from openai import OpenAI

def remove_states_after_reliable(project_id, bug_id, reliable_state=None):
    result_dir = f"result/{project_id}_{bug_id}"
    if not os.path.exists(result_dir):
        return
    
    if reliable_state is None:
        for filename in os.listdir(result_dir):
            if filename.startswith("state_") and filename.endswith(".json"):
                file_path = os.path.join(result_dir, filename)
                try:
                    os.remove(file_path)
                except OSError as e:
                    pass
        return
    
    try:
        rel_method, rel_iteration, rel_phase, rel_step = map(int, reliable_state.split(','))
    except (ValueError, AttributeError):
        return
    
    for filename in os.listdir(result_dir):
        if not (filename.startswith("state_") and filename.endswith(".json")):
            continue
            
        try:
            parts = filename[6:-5].split('_')
            if len(parts) != 4:
                continue
            method, iteration, phase, step = map(int, parts)
        except ValueError:
            continue
        
        should_remove = False
        
        if method > rel_method:
            should_remove = True
        elif method == rel_method:
            if iteration > rel_iteration:
                should_remove = True
            elif iteration == rel_iteration:
                if phase > rel_phase:
                    should_remove = True
                elif phase == rel_phase:
                    if step > rel_step:
                        should_remove = True
        
        if should_remove:
            file_path = os.path.join(result_dir, filename)
            try:
                os.remove(file_path)
            except OSError as e:
                pass

class OpenAIClient():
    def __init__(self):
        self.client = OpenAI(
            base_url="",
            api_key=""
        )
    
    def getResponse(self, **kwargs):
        for _ in range(5):
            try:
                # print(f"new message call. try...")
                response = self.client.chat.completions.create(**kwargs, timeout=60)
                time.sleep(0.2)
                return response
            except Exception as e:
                if "service unavailable" in str(e).lower() or "503" in str(e):
                    print("service unavailable error")
                    time.sleep(1)
                else:
                    print(f"Error occurred: {e}.\n")
                    time.sleep(1)
        raise Exception("Failed to get response in 5 attempts.")

def main():
    if len(sys.argv) < 3:
        # print("Usage: python interaction.py <project_id> <bug_id>")
        sys.exit(1)
    
    project_id = sys.argv[1]
    bug_id = sys.argv[2]
    try:
        with open('user_driven.json', 'r', encoding='utf-8') as f:
            user_data = json.load(f)
        command_type = user_data['command']
    except FileNotFoundError:
        # print("Error: user_driven.json not found")
        sys.exit(1)
    except KeyError:
        # print("Error: 'command' key not found in user_driven.json")
        sys.exit(1)
    except json.JSONDecodeError:
        # print("Error: Invalid JSON format in user_driven.json")
        sys.exit(1)

    if command_type == 0:
        # command: run DebugPilot
        cmd = [sys.executable, "main.py", project_id, bug_id]

        remove_states_after_reliable(project_id, bug_id)
    elif command_type == 1:
        # command: reject
        method_index = user_data["currentIndexMethod"]
        iteration_index = user_data["currentIndexIteration"]

        target_state_file = f"result/{project_id}_{bug_id}/state_{method_index}_{iteration_index}_1_1.json"
        if not os.path.exists(target_state_file):
            sys.exit(1)
        
        reliable_state = None
        
        if iteration_index > 1:
            prev_state_file = f"result/{project_id}_{bug_id}/state_{method_index}_{iteration_index-1}_1_7.json"
            if os.path.exists(prev_state_file):
                reliable_state = f"{method_index},{iteration_index-1},1,7"
        elif iteration_index == 1 and method_index > 1:
            max_ite = 1
            for ite in range(1, 4):
                check_file = f"result/{project_id}_{bug_id}/state_{method_index-1}_{ite}_2_1.json"
                if os.path.exists(check_file):
                    max_ite = ite
            reliable_state = f"{method_index-1},{max_ite},2,1"
        
        if reliable_state:
            remove_states_after_reliable(project_id, bug_id, reliable_state)
            cmd = [sys.executable, "main.py", project_id, bug_id, reliable_state]
        else:
            remove_states_after_reliable(project_id, bug_id)
            cmd = [sys.executable, "main.py", project_id, bug_id]
    elif command_type == 2:
        # command: selection fix
        method_index = user_data["currentIndexMethod"]
        iteration_index = (user_data["currentIndexIteration"] + 1) / 4
        selected = user_data["selectedOption"]

        block_state_file = f"result/{project_id}_{bug_id}/state_{method_index}_{iteration_index}_1_2.json"
        method_state_file = f"result/{project_id}_{bug_id}/state_{method_index}_{iteration_index-1}_2_1.json" if iteration_index > 1 else None
        
        if os.path.exists(block_state_file):
            reliable_state = f"{method_index},{iteration_index},1,1"
            
            remove_states_after_reliable(project_id, bug_id, reliable_state)
            
            cmd1 = [sys.executable, "main.py", project_id, bug_id, reliable_state, "-s", str(selected)]
            try:
                result1 = subprocess.run(cmd1, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as e:
                sys.exit(1)
            
            continue_state = f"{method_index},{iteration_index},1,2"
            cmd2 = [sys.executable, "main.py", project_id, bug_id, continue_state]
            cmd = cmd2
            
        elif method_state_file and os.path.exists(method_state_file):
            reliable_state = f"{method_index},{iteration_index-1},1,7"
            
            remove_states_after_reliable(project_id, bug_id, reliable_state)
            
            cmd1 = [sys.executable, "main.py", project_id, bug_id, reliable_state, "-s", str(selected)]
            try:
                result1 = subprocess.run(cmd1, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as e:
                sys.exit(1)
            
            if (selected != 0):
                continue_state = f"{method_index},{iteration_index-1},2,1"
                cmd2 = [sys.executable, "main.py", project_id, bug_id, continue_state]
                cmd = cmd2
        else:
            sys.exit(1)
    elif command_type == 3:
        # command: insight submit
        method_index = user_data["currentIndexMethod"]
        iteration_index = (user_data["currentIndexIteration"] + 1) / 4
        insight = user_data["context"]
        
        state_1_7_file = f"result/{project_id}_{bug_id}/state_{method_index}_{iteration_index}_1_7.json"
        state_2_1_file = f"result/{project_id}_{bug_id}/state_{method_index}_{iteration_index-1}_2_1.json" if iteration_index > 1 else None
        
        reliable_state = None
        target_state_file = None
        
        if os.path.exists(state_1_7_file):
            reliable_state = f"{method_index},{iteration_index},1,7"
            target_state_file = state_1_7_file

        elif state_2_1_file and os.path.exists(state_2_1_file):
            reliable_state = f"{method_index},{iteration_index-1},2,1"
            target_state_file = state_2_1_file
            
        else:
            sys.exit(1)
        
        try:
            with open(target_state_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            current_context = state_data["result"]["context"]
            new_context = current_context + f"\n\nUser insight:\n{insight}"
            state_data["result"]["context"] = new_context
            
            with open(target_state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=4, ensure_ascii=False)
            
        except FileNotFoundError:
            sys.exit(1)
        except KeyError as e:
            sys.exit(1)
        except json.JSONDecodeError:
            sys.exit(1)
        
        remove_states_after_reliable(project_id, bug_id, reliable_state)
        cmd = [sys.executable, "main.py", project_id, bug_id, reliable_state]
    elif command_type == 4:
        # command: ask
        method_index = user_data["currentIndexMethod"]
        iteration_index = (user_data["currentIndexIteration"] + 1) / 4
        message = user_data["message"]

        if "messages" in user_data and user_data["messages"]:
            messages = user_data["messages"]
        else:
            messages = None
            
            state_1_7_file = f"result/{project_id}_{bug_id}/state_{method_index}_{iteration_index}_1_7.json"
            state_2_1_file = f"result/{project_id}_{bug_id}/state_{method_index}_{iteration_index-1}_2_1.json" if iteration_index > 1 else None
            
            if os.path.exists(state_1_7_file):
                try:
                    with open(state_1_7_file, 'r', encoding='utf-8') as f:
                        state_data = json.load(f)
                    messages = state_data["messages"]
                except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
                    pass
                    
            elif state_2_1_file and os.path.exists(state_2_1_file):
                try:
                    with open(state_2_1_file, 'r', encoding='utf-8') as f:
                        state_data = json.load(f)
                    messages = state_data["messages"]
                except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
                    pass
            
            if messages is None:
                sys.exit(1)

        user_message_count = sum(1 for msg in messages if msg.get("role") == "user")
        if user_message_count >= 20:
            user_data["response"] = "You have reached the maximum interaction limit (20 times). Please manage the session length."
            user_data["messages"] = messages
            
            with open('user_driven.json', 'w', encoding='utf-8') as f:
                json.dump(user_data, f, indent=4, ensure_ascii=False)
            sys.exit(0)

        user_message = {"role": "user", "content": message}
        messages.append(user_message)

        try:
            client = OpenAIClient()
            response = client.getResponse(
                model="gpt-4o",
                messages=messages
            )
            ai_reply = response.choices[0].message.content
            
            assistant_message = {"role": "assistant", "content": ai_reply}
            messages.append(assistant_message)
            
            user_data["response"] = ai_reply
            user_data["messages"] = messages
            
            with open('user_driven.json', 'w', encoding='utf-8') as f:
                json.dump(user_data, f, indent=4, ensure_ascii=False)
            
            
        except Exception as e:
            error_message = f"Error getting LLM response: {str(e)}"
            user_data["response"] = error_message
            user_data["messages"] = messages
            
            with open('user_driven.json', 'w', encoding='utf-8') as f:
                json.dump(user_data, f, indent=4, ensure_ascii=False)
            
            sys.exit(1)
    elif command_type == 5:
        # command: oracle fix
        method_index = user_data["currentIndexMethod"]
        iteration_index = (user_data["currentIndexIteration"] + 1) / 4
        oracle_data = user_data["oracle"]
        if isinstance(oracle_data, str):
            try:
                oracle_items = json.loads(oracle_data)
            except json.JSONDecodeError:
                sys.exit(1)
        else:
            oracle_items = oracle_data
        
        state_1_6_file = f"result/{project_id}_{bug_id}/state_{method_index}_{iteration_index}_1_6.json"
        
        reliable_state = None
        target_state_file = None
        
        if os.path.exists(state_1_6_file):
            reliable_state = f"{method_index},{iteration_index},1,6"
            target_state_file = state_1_6_file
        else:
            sys.exit(1)
        
        try:
            with open(target_state_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            prediction_str = "\"oracle\":\n"
            for oracle in oracle_items:
                prediction_str = prediction_str + f"- \"name\": \"{oracle['name']}\", \"analysis\": \"{oracle['analysis']}\", \"expected\": \"{oracle['expected']}\"\n"

            state_data["result"]["oracle"] = {
                "oracle": oracle_items,
                "prediction_str": prediction_str
            }
            
            with open(target_state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=4, ensure_ascii=False)
            
        except FileNotFoundError:
            sys.exit(1)
        except KeyError as e:
            sys.exit(1)
        except json.JSONDecodeError:
            sys.exit(1)
        
        remove_states_after_reliable(project_id, bug_id, reliable_state)
        cmd = [sys.executable, "main.py", project_id, bug_id, reliable_state]
    elif command_type == 6:
        # command: partition fix
        method_index = user_data["currentIndexMethod"]
        iteration_index = (user_data["currentIndexIteration"] + 2) / 4
        blocks_data = user_data["list"]
        if isinstance(blocks_data, str):
            try:
                blocks = json.loads(blocks_data)
            except json.JSONDecodeError:
                sys.exit(1)
        else:
            blocks = blocks_data
        
        state_1_1_file = f"result/{project_id}_{bug_id}/state_{method_index}_{iteration_index}_1_1.json"
        
        reliable_state = None
        target_state_file = None
        
        if os.path.exists(state_1_1_file):
            reliable_state = f"{method_index},{iteration_index},1,6"
            target_state_file = state_1_1_file
        else:
            sys.exit(1)
        
        try:
            with open(target_state_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            block_list = []
            for block in blocks:
                block_desc = f"- ID: {block['id']}, Line {block['start_line']}-{block['end_line']}: {block['comment']}"
                block_list.append(block_desc)

            state_data["result"]["list"]["blocks"] = blocks
            state_data["result"]["list"]["list"] = block_list

            with open(target_state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=4, ensure_ascii=False)
            
        except FileNotFoundError:
            sys.exit(1)
        except KeyError as e:
            sys.exit(1)
        except json.JSONDecodeError:
            sys.exit(1)
        
        remove_states_after_reliable(project_id, bug_id, reliable_state)
        cmd = [sys.executable, "main.py", project_id, bug_id, reliable_state]


    if 'cmd' not in locals():
        sys.exit(0)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        cmd_summary = [sys.executable, "summary.py", project_id, bug_id]
        result = subprocess.run(cmd_summary, capture_output=True, text=True, check=True)
        cmd_summary = [sys.executable, "summary_enhance.py", project_id, bug_id]
        result = subprocess.run(cmd_summary, capture_output=True, text=True, check=True)
        # print(result.stdout)
        # if result.stderr:
            # print(f"Error: {result.stderr}")
    except subprocess.CalledProcessError as e:
        # print(f"Command failed with return code {e.returncode}")
        # print(f"Error: {e.stderr}")
        pass
    except FileNotFoundError:
        # print("Error: main.py not found or Python not in PATH")
        pass

if __name__ == "__main__":
    main()