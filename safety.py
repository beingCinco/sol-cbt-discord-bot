def check_safety(message: str) -> bool:
  """Block harmful content"""
  red_flags = ["suicide", "self-harm", "kill myself", "end it all"]
  return not any(flag in message.lower() for flag in red_flags)

def crisis_response() -> str:
  """Emergency resources"""
  return (
      "🚨 I care about your safety. Please contact these resources immediately:\n"
      "• National Suicide Prevention Lifeline: 1-800-273-8255\n"
      "• Crisis Text Line: Text HOME to 741741\n"
      "• International Association for Suicide Prevention: https://www.iasp.info/resources/Crisis_Centres/"
  )