# Core 8B base measurement — G1 function-calling + G2 code correctness (G4 band data).
# Pre-registered in docs/CORE8B_PREREGISTRATION.md. Runs in-process, 4-bit, on shinobi.
import json, re, time, sys
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

NODE = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1")
import os as _os
_ONLY = _os.environ.get("CORE8B_ONLY", "")
MODELS = {
    "qwen3-8b": r"C:\Users\User\hf_models\qwen3-8b-normal",
    "dsr1-8b": r"C:\Users\User\hf_models\dsr1-8b-normal",
}
if _ONLY:
    MODELS = {k: v for k, v in MODELS.items() if k in _ONLY.split(",")}

# ---------- G1: function calling (10 prompts) ----------
TOOLS = [
 {"type":"function","function":{"name":"get_weather","description":"Get current weather for a city",
   "parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}},
 {"type":"function","function":{"name":"calculator","description":"Evaluate a math expression",
   "parameters":{"type":"object","properties":{"expression":{"type":"string"}},"required":["expression"]}}},
 {"type":"function","function":{"name":"read_file","description":"Read a file from disk",
   "parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
 {"type":"function","function":{"name":"send_email","description":"Send an email",
   "parameters":{"type":"object","properties":{"to":{"type":"string"},"subject":{"type":"string"},"body":{"type":"string"}},
   "required":["to","subject","body"]}}},
 {"type":"function","function":{"name":"search_web","description":"Search the web",
   "parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
]
G1 = [
 ("What's the weather in Tokyo?", "get_weather", ["city"]),
 ("Calculate 47*93+12", "calculator", ["expression"]),
 ("Read the config at /etc/app/settings.yaml", "read_file", ["path"]),
 ("Email bob@example.com with subject 'Invoice' and body 'Please find attached'", "send_email", ["to","subject","body"]),
 ("Search for the latest news about quantum computing", "search_web", ["query"]),
 ("I need today's forecast for São Paulo", "get_weather", ["city"]),
 ("What is (128*4)/16?", "calculator", ["expression"]),
 ("Open the file C:\\logs\\error.txt and show me", "read_file", ["path"]),
 ("Send a note to alice@corp.io, subject 'Meeting', body 'Tomorrow 10am'", "send_email", ["to","subject","body"]),
 ("Find reviews for the Sony WH-1000XM5", "search_web", ["query"]),
]

# ---------- G2: code correctness (20 problems, execution-verified) ----------
G2 = [
 ("def reverse_string(s):\n    \"\"\"Return the reversed string.\"\"\"",
  [("hello","olleh"),("", ""),("abc","cba")]),
 ("def fizzbuzz(n):\n    \"\"\"Return list of 1..n with fizz/buzz rules.\"\"\"",
  [(3,["1","2","Fizz"]),(5,["1","2","Fizz","4","Buzz"]),(15,["1","2","Fizz","4","Buzz","Fizz","7","8","Fizz","Buzz","11","Fizz","13","14","FizzBuzz"])]),
 ("def two_sum(nums, target):\n    \"\"\"Return indices of the two numbers adding to target.\"\"\"",
  [([2,7,11,15],9,(0,1)),([3,2,4],6,(1,2)),([3,3],6,(0,1))]),
 ("def is_palindrome(s):\n    \"\"\"True if s is a palindrome ignoring case and spaces.\"\"\"",
  [("A man a plan a canal Panama",True),("hello",False),("",True)]),
 ("def binary_search(arr, x):\n    \"\"\"Return index of x in sorted arr or -1.\"\"\"",
  [([1,3,5,7,9],5,2),([1,3,5],4,-1),([],3,-1)]),
 ("def flatten(nested):\n    \"\"\"Flatten arbitrarily nested lists.\"\"\"",
  [([1,[2,[3,4]],5],[1,2,3,4,5]),([],[]),([[[]]],[])]),
 ("def word_count(text):\n    \"\"\"Return dict word->count (lowercased).\"\"\"",
  [("a b a",{"a":2,"b":1}),("",{}),("x x x",{"x":3})]),
 ("def dedupe_keep_order(lst):\n    \"\"\"Remove duplicates keeping first occurrence.\"\"\"",
  [([1,2,1,3,2],[1,2,3]),([],[]),(["a","a"],["a"])]),
 ("def sum_even(nums):\n    \"\"\"Sum of even numbers in list.\"\"\"",
  [([1,2,3,4,5,6],12),([],0),([2,2],4)]),
 ("def max_subarray(nums):\n    \"\"\"Maximum subarray sum (Kadane).\"\"\"",
  [([-2,1,-3,4,-1,2,1,-5,4],6),([1],1),([-1,-2],-1)]),
 ("def count_vowels(s):\n    \"\"\"Count vowels in s.\"\"\"",
  [("hello",2),("",0),("AEIOU",5)]),
 ("def chunk(lst, n):\n    \"\"\"Split lst into chunks of size n.\"\"\"",
  [([1,2,3,4,5],2,[[1,2],[3,4],[5]]),([],3,[]),([1,2],4,[[1,2]])]),
 ("def is_anagram(a, b):\n    \"\"\"True if a and b are anagrams.\"\"\"",
  [("listen","silent",True),("a","b",False),("","" ,True)]),
 ("def first_unique(s):\n    \"\"\"Index of first non-repeating char or -1.\"\"\"",
  [("leetcode",0),("loveleetcode",2),("aabb",-1)]),
 ("def rotate_right(lst, k):\n    \"\"\"Rotate list right by k.\"\"\"",
  [([1,2,3,4,5],2,[4,5,1,2,3]),([1],3,[1]),([],1,[])]),
 ("def rle(s):\n    \"\"\"Run-length encode: 'aab' -> 'a2b1'.\"\"\"",
  [("aab","a2b1"),("", ""),("aaaa","a4")]),
 ("def gcd(a, b):\n    \"\"\"Greatest common divisor.\"\"\"",
  [(12,18,6),(5,0,5),(17,13,1)]),
 ("def to_roman(n):\n    \"\"\"Convert 1-3999 to Roman numerals.\"\"\"",
  [(9,"IX"),(40,"XL"),(1994,"MCMXCIV")]),
 ("def pascal(n):\n    \"\"\"First n rows of Pascal's triangle.\"\"\"",
  [(1,[[1]]),(3,[[1],[1,1],[1,2,1]]),(0,[])]),
 ("def balanced(s):\n    \"\"\"True if brackets (),[],{} balanced.\"\"\"",
  [("({[]})",True),("(]",False),("",True)]),
]

def run_g1(chat_fn):
    ok = 0
    for prompt, want_tool, want_args in G1:
        out = chat_fn(prompt, tools=TOOLS)
        m = re.search(r'\{[\s\S]*\}', out or "")
        good = False
        if m:
            try:
                obj = json.loads(m.group(0))
                name = obj.get("name") or obj.get("function", {}).get("name") or obj.get("tool")
                args = obj.get("arguments") or obj.get("parameters") or obj.get("function", {}).get("arguments") or obj
                if name == want_tool and all(k in json.dumps(args) for k in want_args):
                    good = True
            except Exception:
                pass
        if "<tool_call>" in (out or "") and want_tool in (out or ""):
            good = good or True
        ok += good
    return ok, len(G1)

def run_g2(chat_fn):
    ok = 0
    for sig, tests in G2:
        good = False
        for attempt in range(2):
            out = chat_fn(f"Write this Python function. Reply with ONLY the code, no markdown fences, no explanation:\n{sig}", temp=0.2)
            code = re.sub(r"```[a-z]*|```", "", out or "").strip()
            try:
                ns = {}
                exec(code, ns)
                fn = [v for k, v in ns.items() if callable(v) and not k.startswith("__")][0]
                allok = True
                for t in tests:
                    args, expected = t[:-1], t[-1]
                    got = fn(*args)
                    if got != expected:
                        allok = False
                        break
                if allok:
                    good = True
                    break
            except Exception:
                pass
        ok += good
    return ok, len(G2)

def main():
    results = {}
    for name, path in MODELS.items():
        print(f"[core8b] loading {name} ...", flush=True)
        tok = AutoTokenizer.from_pretrained(path)
        model = AutoModelForCausalLM.from_pretrained(
            path, torch_dtype=torch.bfloat16, load_in_4bit=True,
            device_map="auto", trust_remote_code=True)
        model.eval()

        def chat_fn(prompt, tools=None, temp=0.2):
            msgs = [{"role": "system", "content": "You are a helpful engineering assistant."}]
            if tools:
                msgs.append({"role": "system", "content":
                    "Available tools (JSON): " + json.dumps(tools) +
                    ". To call a tool, output a JSON object with fields name and arguments."})
            msgs.append({"role": "user", "content": prompt})
            kw = {}
            try:
                tok.apply_chat_template(msgs, tokenize=False,
                                        add_generation_prompt=True, enable_thinking=False)
                kw["enable_thinking"] = False
            except TypeError:
                pass
            text = tok.apply_chat_template(msgs, tokenize=False,
                                           add_generation_prompt=True, **kw)
            ids = tok(text, return_tensors="pt").to(model.device)
            with torch.no_grad():
                o = model.generate(**ids, max_new_tokens=400, do_sample=temp > 0,
                                  temperature=temp, top_p=0.9,
                                  pad_token_id=tok.eos_token_id)
            out = tok.decode(o[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
            out = re.sub(r"During[\s\S]*?During|During[\s\S]*$", "", out).strip()
            if "" not in out and out.count("During") > 0:
                out = "" 
            out = re.sub(r"<think>[\s\S]*?</think>", "", out).strip()
            return out

        g1ok, g1n = run_g1(chat_fn)
        print(f"[core8b] {name}: G1 function-calling {g1ok}/{g1n}", flush=True)
        g2ok, g2n = run_g2(chat_fn)
        print(f"[core8b] {name}: G2 code-correctness {g2ok}/{g2n}", flush=True)
        results[name] = {"g1_fn_call": g1ok / g1n, "g2_code": g2ok / g2n,
                         "composite": round((g1ok / g1n + g2ok / g2n) / 2, 4)}
        del model
        torch.cuda.empty_cache()
    results["ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
    results["bars"] = {"trained_g1": 0.8, "trained_g2": 0.7,
                       "band": "40-70% composite preferred for trainability"}
    (NODE / "core8b_base_eval_qwen3_g2fix.json").write_text(json.dumps(results, indent=1))
    print(json.dumps(results, indent=1), flush=True)

if __name__ == "__main__":
    main()
