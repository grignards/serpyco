#include <string>

#include <valijson/schema.hpp>
#include <valijson/validator.hpp>

class PyValijson
{
  public:
    PyValijson(const std::string &schema);

    bool validate(const std::string &data);

  private:
    valijson::Schema m_schema;
    valijson::Validator m_validator;
};