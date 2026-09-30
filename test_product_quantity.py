from graph.dynamic_workflow import dynamic_agent

r = dynamic_agent.invoke({
    'question': 'Show product quantity for 08-2026'
})

print('INTENT =', r.get('intent'))
print('GROUP_BY =', r.get('group_by'))
print('AGGREGATE =', r.get('aggregate_function'))
print('AGGREGATE_COLUMN =', r.get('aggregate_column'))
print('REQUESTED_COLUMNS =', r.get('requested_columns'))
print('RESULT =', r.get('result'))
print('ROW_COUNT =', r.get('row_count'))
