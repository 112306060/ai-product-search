from modules.website_classifier import classify_website

sample_text = """
Green People is a natural and organic beauty brand.
We produce organic shampoo and natural hair care products.
"""

result = classify_website(
    "https://greenpeople.eu",
    sample_text
)

print(result)