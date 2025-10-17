code design guide lines:

 - singal source of truth: if there are queries  int the code consolidate them into 1 source using singal data class.
-  data classes: 
    - put all fucntion it used as member functions
    - call process once in code, then pass it as refernce

1. tasks list: 
    1.1 break this prompt into small simple tasks first and list them
    1.2 five this task list a name
    1.3 put list into file under .cursor/plans/ of this repo

2. task list review:
    2.1 run over the tasks list item
        2.1.1 pet task item: list what file are involve and update.

3. task list global review:
    3.1 udpate tasks to
        3.1.2 keep files under aprox ~400 lines by:
            3.1.2.1 reuse fucntions
            3.1.2.2 if needed: create helper function in new files
            3.1.2.3 cache operation into line at start of functions if rused a lot.



execute the task list:
4. after each task completion: comment under the task what did you do in the task. 

6. after completion:
    6.1 review readme file in repo and update them
