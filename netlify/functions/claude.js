// Netlify Function: 멀티 AI 프로바이더 프록시 (Claude / OpenAI / Gemini)
exports.handler = async (event) => {
  if (event.httpMethod !== 'POST') return { statusCode: 405, body: 'Method Not Allowed' };
  try {
    const { provider, system, user, apiKey } = JSON.parse(event.body);
    const prov = provider || 'claude';
    const envKey = {
      claude: process.env.ANTHROPIC_API_KEY,
      openai: process.env.OPENAI_API_KEY,
      gemini: process.env.GEMINI_API_KEY
    }[prov];
    const key = apiKey || envKey;
    if (!key) return resp(400, { error: '선택한 AI의 API 키가 없습니다. 🔑 버튼을 눌러 키를 입력해 주세요.' });

    let text;
    if (prov === 'claude') text = await callClaude(key, system, user);
    else if (prov === 'openai') text = await callOpenAI(key, system, user);
    else if (prov === 'gemini') text = await callGemini(key, system, user);
    else return resp(400, { error: '알 수 없는 AI 제공자입니다.' });

    return resp(200, { text });
  } catch (err) {
    return resp(500, { error: err.message });
  }
};

function resp(code, body) {
  return { statusCode: code, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
}

async function callClaude(key, system, user) {
  const r = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-api-key': key, 'anthropic-version': '2023-06-01' },
    body: JSON.stringify({ model: 'claude-sonnet-4-6', max_tokens: 4000, system, messages: [{ role: 'user', content: user }] })
  });
  const d = await r.json();
  if (!r.ok) throw new Error(d.error?.message || 'Claude 오류 ' + r.status);
  return d.content[0].text;
}

async function callOpenAI(key, system, user) {
  const r = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key },
    body: JSON.stringify({ model: 'gpt-4o', max_tokens: 4000, messages: [{ role: 'system', content: system }, { role: 'user', content: user }] })
  });
  const d = await r.json();
  if (!r.ok) throw new Error(d.error?.message || 'OpenAI 오류 ' + r.status);
  return d.choices[0].message.content;
}

async function callGemini(key, system, user) {
  const url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=' + key;
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ contents: [{ parts: [{ text: system + '\n\n' + user }] }], generationConfig: { temperature: 0.4, maxOutputTokens: 4000 } })
  });
  const d = await r.json();
  if (!r.ok) throw new Error(d.error?.message || 'Gemini 오류 ' + r.status);
  return d.candidates?.[0]?.content?.parts?.[0]?.text || '';
}
