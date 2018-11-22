import serpyco.val

print("STRING")
schema = serpyco.val.compile({"type": "string", "pattern": "hel", "minimumLength": 3})
serpyco.val.validate(schema, "hello")
serpyco.val.validate(schema, 2)
serpyco.val.validate(schema, "aa")

print("OBJECT")
schema = serpyco.val.compile(
    {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}
)
serpyco.val.validate(schema, "hello")
serpyco.val.validate(schema, {"name": "hello"})
serpyco.val.validate(schema, {})

print("ARRAY")
schema = serpyco.val.compile({"type": "array", "items": {"type": "string"}})
serpyco.val.validate(schema, "hello")
serpyco.val.validate(schema, ["hello", "world"])
serpyco.val.validate(schema, [42])
