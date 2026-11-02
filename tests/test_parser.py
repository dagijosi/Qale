import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.code_parser import CodeParser

def run_tests():
    parser = CodeParser()
    
    test_cases = [
        ("backslash", {"type": "text", "content": "\\"}),
        ("path backslash to backslash folder", {"type": "text", "content": "path\\to\\folder"}),
        ("go back", {"type": "action", "action": "ACTION_BACKSPACE", "count": 1}),
        ("erase that", {"type": "action", "action": "ACTION_BACKSPACE", "count": 1}),
        ("go back 3 times", {"type": "action", "action": "ACTION_BACKSPACE", "count": 3}),
        ("new line", {"type": "action", "action": "ACTION_ENTER", "count": 1}),
        ("I love snick js and react js", {"type": "text", "content": "I love Next.js and React"}),
        ("we are using neck js for this project", {"type": "text", "content": "we are using Next.js for this project"}),
        ("install type script and mongo db", {"type": "text", "content": "install TypeScript and MongoDB"}),
        ("camel case fetch user profile", {"type": "text", "content": "fetchUserProfile"}),
        ("camelCase, getUserAccount detail,", {"type": "text", "content": "getUserAccountDetail"}),
        ("snake case get user by id", {"type": "text", "content": "get_user_by_id"}),
        ("curly braces", {"type": "text", "content": "{}"}),
        ("fat arrow", {"type": "text", "content": "=>"}),
        ("strictly equals", {"type": "text", "content": "==="}),
        ("semicolon", {"type": "text", "content": ";"}),
        ("in, hello world, go back.", {"type": "action", "action": "ACTION_BACKSPACE", "count": 1}),
        ("I have been working for months. The main goal is simple.", {"type": "text", "content": "I have been working for months. The main goal is simple."}),
        ("using nest js and postgres sql and tanstack query", {"type": "text", "content": "using NestJS and PostgreSQL and TanStack Query"}),
        ("create file app. config. ts", {"type": "text", "content": "create file app.config.ts"}),
        ("assign value https colon slash slash api dot example dot com slash v1", {"type": "text", "content": "assign value https://api.example.com/v1"}),
        ("define constant named API URL", {"type": "text", "content": "define constant named API_URL"}),
        ("create a function called get user by id", {"type": "text", "content": "create a function called getUserById"}),
        ("using Dustand and NIST.js and Postgres.js", {"type": "text", "content": "using Zustand and NestJS and PostgreSQL"}),
        ("subscription costs 499 per", {"type": "text", "content": "subscription costs 499 birr"}),
        ("good thing.us ordinary texts", {"type": "text", "content": "good thing. us ordinary texts"}),
        ("rate from 2.5 to 2.5 to 2.5 to 2.5 to 2 percent", {"type": "text", "content": "rate from 2.5 to 2 percent"}),
        ("traceful api", {"type": "text", "content": "RESTful api"}),
        ("Telman CSS", {"type": "text", "content": "Tailwind CSS"}),
        ("the main goal of the store", {"type": "text", "content": "the main goal of the store"}),
        ("my name is dagmawi yoseph", {"type": "text", "content": "my name is Dagmawi Yoseph"}),
        ("written by dag mawi joseph in addis ababa", {"type": "text", "content": "written by Dagmawi Yoseph in Addis Ababa"}),
        ("from ethiopia and kenya", {"type": "text", "content": "from Ethiopia and Kenya"}),
        ("contact bekele or dawit", {"type": "text", "content": "contact Bekele or Dawit"}),
        # New Actions
        ("escape", {"type": "action", "action": "ACTION_ESCAPE", "count": 1}),
        ("press escape", {"type": "action", "action": "ACTION_ESCAPE", "count": 1}),
        ("select all", {"type": "action", "action": "ACTION_SELECT_ALL", "count": 1}),
        ("copy that", {"type": "action", "action": "ACTION_COPY", "count": 1}),
        ("cut that", {"type": "action", "action": "ACTION_CUT", "count": 1}),
        ("undo that", {"type": "action", "action": "ACTION_UNDO", "count": 1}),
        # New Casing Converters
        ("title case user payment record", {"type": "text", "content": "User Payment Record"}),
        ("train case header request token", {"type": "text", "content": "Header-Request-Token"}),
        ("dot case core module config", {"type": "text", "content": "core.module.config"}),
        # Modern Developer Syntax & Operators
        ("nullish coalescing", {"type": "text", "content": "??"}),
        ("optional chaining", {"type": "text", "content": "?."}),
        ("spread operator", {"type": "text", "content": "..."}),
        ("strictly not equals", {"type": "text", "content": "!=="}),
        ("not equals", {"type": "text", "content": "!="}),
        ("plus equals", {"type": "text", "content": "+="}),
        ("increment", {"type": "text", "content": "++"}),
        ("decrement", {"type": "text", "content": "--"}),
        # Comments & Code Blocks
        ("comment setup database client", {"type": "text", "content": "// setup database client"}),
        ("hash comment define environment port", {"type": "text", "content": "# define environment port"}),
        ("triple backticks", {"type": "text", "content": "```"}),
        ("local host colon 3000", {"type": "text", "content": "localhost:3000"}),
    ]
    
    passed = 0
    for inp, expected in test_cases:
        result = parser.parse(inp)
        assert result == expected, f"FAILED for '{inp}': Got {result}, expected {expected}"
        passed += 1
        print(f" [PASS] '{inp}' -> {result}")

    print(f"\nAll {passed}/{len(test_cases)} test cases passed successfully!")

if __name__ == "__main__":
    run_tests()
