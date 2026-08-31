# Magic prompt templates and default negative prompt.
# Ported verbatim from the original Prompt Quill (llama_index_pq/pq/settings/defaults.py).

PROMPT_TEMPLATE_A = """{instruction_start}Context information is below.
---------------------
{context_str}
---------------------
Given the context information and not prior knowledge,
create a text to image prompt based on the context and the Query, don"t mind if the context does not match the Query, still try to create a wonderful text to image prompt.
You also take care of describing the scene, the lighting as well as the quality improving keywords
{start_pattern}USER: translation in major world languages, machinery of translation in various specializations, cyberpunk style
ASSISTANT: Cyberpunk-style illustration, featuring a futuristic translation device in various specializations, set against a backdrop of neon-lit cityscape. The device, adorned with glowing circuits and cybernetic enhancements, showcases its capabilities in translating languages such as English, Mandarin, Spanish, French, and Arabic. The scene is illuminated by the warm glow of streetlights and the pulsing neon signs, casting intricate shadows on the surrounding machinery. The artwork is rendered in high-quality, vivid colors, with detailed textures and sharp lines, evoking the gritty yet mesmerizing atmosphere of the cyberpunk world.
{start_pattern}USER: a man walking moon
ASSISTANT: cinematic photo, high resolution, masterpiece, ((man walking on the moon)), in a surrealistic setting, with the moon"s surface featuring vivid colors and abstract patterns, the man wearing a spacesuit with an astronaut helmet, the American flag planted on the moon"s surface in the background, the Earth visible in the distance, the scene illuminated by the moon"s glow, on eye level, scenic, masterpiece.
{start_pattern}USER: a female witch
ASSISTANT: The scene unfolds with the beautiful female witch standing on the rooftop of an ancient castle, her black cloak billowing in the wind as she gazes out at the breathtaking view below. The midnight sky above is filled with stars and the full moon casts an eerie glow on the witch"s face, highlighting her enchanting beauty. She stands tall, her hood framing her face, casting a spell with her outstretched hand, her dark aura swirling around her. The castle walls, adorned with intricate carvings and gargoyles, stand tall behind her, adding to the mystical atmosphere of the scene. The wind whispers through the rooftop"s crenellations, creating an eerie yet captivating soundtrack for this magical moment. The quality of the photo is exceptional, with every detail of the witch"s cloak, the castle"s architecture, and the night sky captured in stunning clarity. This cinematic masterpiece invites the viewer to step into the world of magic and mystery, leaving them in awe of the beautiful female witch standing on the castle rooftop under the starry sky.
{start_pattern}USER: artificial intelligence and human
ASSISTANT: High-quality digital art, blending fantasy and reality, ((artificial intelligence)) and (((human))), in a futuristic cityscape, an AI robot with glowing circuits standing alongside a confident, well-dressed human, both exuding intelligence and grace, the AI with a sleek metal body and the human with impeccable style, the cityscape filled with advanced technology and vibrant colors, dynamic lighting, surreal and thought-provoking, on eye level, scenic, masterpiece.
{start_pattern}USER: futuristic combat zone
ASSISTANT: cinematic photo, masterpiece, in the style of Blade Runner, futuristic combat zone, at dusk, showcasing a high-tech battlefield with neon lights illuminating the scene, filled with advanced mechs and soldiers engaged in an intense fight, the air filled with stunning lighting effects, on eye level, dramatic, masterpiece, ultra high resolution, dynamic anime-style fight scene, with a focus on the sleek design of the combat gear and the fluidity of the movements, capturing the essence of sci-fi action in a visually stunning manner.
{user_pattern}USER: Create a prompt for: {query_str}
{assistant_pattern}"""

PROMPT_TEMPLATE_B = """{instruction_start}Context information is below.
---------------------
{context_str}
---------------------
Given the context information and not prior knowledge,
Objective: Generate text-to-image prompts as comma-separated lists of concepts.
Instructions:
1. Each prompt should be a comma-separated list of concepts.
2. Include diverse and vivid concepts that can be visualized in an image.
3. Each list should contain between 3 to 20 concepts no longer than 4 words.
4. The concepts should be related to a common theme or subject.
5. You do not tell a story
6. you do not use any stop words
7. Your role is named "ASSISTANT"
{start_pattern}USER: a nice kitten
ASSISTANT: Adorable digital illustration, featuring a cute, fluffy kitten with big, bright eyes, curled up in a cozy blanket, with its paws tucked neatly beneath its body, the kitten"s fur so soft and inviting that one can"t resist the urge to reach out and pet it, rendered in high resolution and vibrant colors, on eye level, masterpiece.
{start_pattern}USER: a man walking moon
ASSISTANT: cinematic photo, high resolution, masterpiece, ((man walking on the moon)), in a surrealistic setting, with the moon"s surface featuring vivid colors and abstract patterns, the man wearing a spacesuit with an astronaut helmet, the American flag planted on the moon"s surface in the background, the Earth visible in the distance, the scene illuminated by the moon"s glow, on eye level, scenic, masterpiece.
{start_pattern}USER: artificial intelligence and human
ASSISTANT: High-quality digital art, blending fantasy and reality, ((artificial intelligence)) and (((human))), in a futuristic cityscape, an AI robot with glowing circuits standing alongside a confident, well-dressed human, both exuding intelligence and grace, the AI with a sleek metal body and the human with impeccable style, the cityscape filled with advanced technology and vibrant colors, dynamic lighting, surreal and thought-provoking, on eye level, scenic, masterpiece.
{start_pattern}USER: futuristic combat zone
ASSISTANT: at dusk, cinematic photo in the style of Blade Runner, with a high-tech battlefield illuminated by neon lights, featuring advanced mechs and soldiers engaged in an intense fight, the air filled with stunning lighting effects, on eye level, dramatic, masterpiece, ultra high resolution, dynamic anime-style fight scene, capturing the essence of sci-fi action in a visually stunning manner, with a focus on the sleek design of the combat gear and the fluidity of the movements, evoking the gritty yet mesmerizing atmosphere of the cyberpunk world.
{user_pattern}USER: Create a prompt for: {query_str}
{assistant_pattern}"""

PROMPT_TEMPLATES = {"a": PROMPT_TEMPLATE_A, "b": PROMPT_TEMPLATE_B}

DEFAULT_NEGATIVE_PROMPT = """out of frame, lowres, text, error, cropped, worst quality, low quality, jpeg artifacts, ugly, duplicate, morbid, mutilated, out of frame, extra fingers, mutated hands, poorly drawn hands, poorly drawn face, mutation, deformed, blurry, dehydrated, bad anatomy, bad proportions, extra limbs, cloned face, disfigured, gross proportions, malformed limbs, missing arms, missing legs, extra arms, extra legs, fused fingers, too many fingers, long neck, username, watermark, signature"""
