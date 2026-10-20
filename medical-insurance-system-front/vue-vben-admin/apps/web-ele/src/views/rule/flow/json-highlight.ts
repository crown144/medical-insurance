const escapeHtml = (text: any): string => {
  if (text === null || text === undefined) return '';
  const map: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  };
  return String(text).replaceAll(/[&<>"']/g, (m) => map[m] ?? m);
};

// 递归将 JSON 转为带高亮的 HTML
export const jsonToHtml = (
  data: any,
  currentPath: string = '$',
  indentLevel: number = 0,
  highlightPaths: ReadonlySet<string> = new Set(),
): string => {
  const indent = '  '.repeat(indentLevel);
  const nextIndent = '  '.repeat(indentLevel + 1);

  let content = '';
  if (data === null) content = `<span class="json-null">null</span>`;
  else if (typeof data === 'string')
    content = `<span class="json-string">"${escapeHtml(data)}"</span>`;
  else if (typeof data === 'number')
    content = `<span class="json-number">${data}</span>`;
  else if (typeof data === 'boolean')
    content = `<span class="json-boolean">${data}</span>`;
  else if (Array.isArray(data)) {
    if (data.length === 0) return '[]';
    const items = data
      .map((item, index) => {
        const itemPath = `${currentPath}[${index}]`;
        return `${nextIndent}${jsonToHtml(item, itemPath, indentLevel + 1, highlightPaths)}`;
      })
      .join(',\n');
    return `[\n${items}\n${indent}]`;
  } else if (typeof data === 'object') {
    const entries = Object.entries(data);
    if (entries.length === 0) return '{}';
    const items = entries
      .map(([key, value]) => {
        const keyHtml = `<span class="json-key">"${escapeHtml(key)}"</span>`;
        const itemPath = `${currentPath}.${key}`; // 简单路径构建
        const valueHtml = jsonToHtml(
          value,
          itemPath,
          indentLevel + 1,
          highlightPaths,
        );
        return `${nextIndent}${keyHtml}: ${valueHtml}`;
      })
      .join(',\n');
    return `{\n${items}\n${indent}}`;
  }

  // 匹配高亮路径 (这里做简单的包含匹配模拟)
  // 实际项目中可以使用 jsonpath 库来精确匹配
  if (highlightPaths.has(currentPath)) {
    return `<mark class="highlight-evidence">${content}</mark>`;
  }
  return content;
};
