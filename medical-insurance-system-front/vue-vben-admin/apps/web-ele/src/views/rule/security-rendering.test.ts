import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import SourceText from './SourceText.vue';
import { jsonToHtml } from './flow/json-highlight';

const attack =
  '<img src=x onerror="window.__xss=1"><svg onload="window.__xss=2"></svg><script>window.__xss=3</script>';

describe('untrusted rule content', () => {
  it('shows stored source markup literally without executable elements', async () => {
    const wrapper = mount(SourceText, { props: { content: attack } });
    expect(wrapper.text()).toBe(attack);
    expect(wrapper.find('img, svg, script, iframe, a').exists()).toBe(false);
    await wrapper.setProps({
      content: '<a href="javascript:alert(1)">来源</a>',
    });
    expect(wrapper.find('a').exists()).toBe(false);
    wrapper.unmount();
  });

  it('escapes nested JSON keys and values while retaining evidence highlighting', () => {
    const value = {
      [attack]: [attack, { '<iframe srcdoc="x">': '&lt;script&gt;' }],
    };
    const root = document.createElement('div');
    root.innerHTML = jsonToHtml(value, '$', 0, new Set([`$.${attack}[0]`]));
    expect(root.querySelector('img, svg, script, iframe')).toBeNull();
    expect(root.querySelector('mark')?.textContent).toBe(`"${attack}"`);
    expect(root.textContent).toContain(`"${attack}":`);
    expect(root.textContent).toContain('&lt;script&gt;');
    expect(root.querySelector('.json-key')).not.toBeNull();
  });
});
