#include <rapidjson/document.h>

#include <valijson/adapters/rapidjson_adapter.hpp>
#include <valijson/utils/rapidjson_utils.hpp>
#include <valijson/schema_parser.hpp>

#include "valijson.h"

using valijson::Schema;
using valijson::SchemaParser;
using valijson::Validator;
using valijson::adapters::RapidJsonAdapter;

PyValijson::PyValijson(const std::string &schema)
{
    rapidjson::Document document;
    document.parse(schema.c_str());

    // Parse JSON schema content using valijson
    SchemaParser parser;
    RapidJsonAdapter mySchemaAdapter(document);
    parser.populateSchema(mySchemaAdapter, m_schema);
}

bool PyValijson::validate(const std::string &data)
{
    rapidjson::Document document;
    document.parse(data.c_str());
    RapidJsonAdapter adapter(document);
    return m_validator.validate(m_schema, adapter, NULL));
}
