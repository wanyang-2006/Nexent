import html
import json
from pathlib import Path

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parent.parent
path = ROOT / '05_来源核验/cases.json'
cases = json.loads(path.read_text(encoding='utf-8'))
for case in cases:
    if case['id'] == 'T01':
        case['evidence'] = '本次已读取官方获奖名单及作品文章，作者UID与文章链接对应'
    if case['id'] in ['T03', 'T04', 'T05']:
        case['evidence'] = '待核实线索：当前官网仅返回动态页面外壳，未取得具体作品正文；不纳入已核实作品'
        case['award'] = '未核实作品条目与奖项，仅保留后续检索线索'

for ident, name, article, award, fact, adapt in [
    ('T10', 'FlowLens企业流程智能解读助手', '2609285', '最佳作者奖', '公开概述说明意图识别、知识库拆分与工作流；页面可见入职、报销、资产领用场景目录。', '制造SOP或政务材料流程的版本更新与证据核验'),
    ('T11', '企业知识库问答助手', '2609061', '优秀作者奖', '作者提供知识库配置教程与提示词，并说明某发布渠道引用链接显示存在限制。', '把规范查询升级成制造变更影响分析，检查最终界面的证据链接可用性'),
    ('T12', '一句话算工资', '2607845', '优秀作者奖', '公开概述是跨城市税后工资与社保公积金计算。', '借鉴确定性计算工具，改为政务政策版本变化的计算核验'),
]:
    if not any(c['id'] == ident for c in cases):
        cases.append(dict(id=ident, group='腾讯云', name=name, event='腾讯元器地球Online智能体开发大赛企业副本赛道，2025—2026', award=award, source='https://cloud.tencent.com/developer/article/2594493', detail='https://cloud.tencent.com/developer/article/'+article, evidence='官方名单与作品文章对应，本次读取确认', fact=fact, resources='作品文章及官方名单；未取得完整源代码', fit='中高', adapt=adapt, gap='原作品未证明具备动态本体；改造建议是本报告提出'))

manual = 'local:04_技术与数据/已下载资料/华为ICT第十届官方手册.pdf'
for ident, name, event, award, page, fact in [
    ('I16', '智慧农业巡检机器人', '第八届2023—2024华为ICT创新赛全球总决赛', '特等奖，华中师范大学', 6, '融合巡检与病害识别；本届行业范围不同，只作真实需求和工程演示参考。'),
    ('I17', 'MindSpore智能问诊医药系统', '第八届华为ICT创新赛全球总决赛（手册上下文）', '三等奖，华中师范大学', 6, '社区常见病问诊与急救知识服务；本届可转为资料核查，不照搬诊疗输出。'),
    ('I18', '盲人辅助出行与监测系统', '第九届2024—2025华为ICT创新赛全球总决赛', '一等奖，华中师范大学', 6, 'AI视觉、北斗定位、传感融合；本届适配度较低。'),
    ('I19', '中小学生编程平台', '第六届2021—2022华为ICT创新赛全球总决赛', '特等奖，厦门大学TCI队', 17, '积木编程与LiteOS编译烧录；可学习用户调研及工程取舍。'),
    ('I20', 'FollowU：基于华为IOT小车的智能跟拍系统', '第六届2021—2022华为ICT创新赛全球总决赛', '特等奖，北京交通大学', 19, '目标跟踪、移动端控制和云存储；可参考软硬件闭环和演示方式。'),
]:
    if not any(c['id'] == ident for c in cases):
        cases.append(dict(id=ident, group='历届华为ICT', name=name, event=event, award=award, source=manual+'#page='+str(page), detail='', evidence='已下载华为官方手册，PDF第'+str(page)+'页（不是印刷页码）', fact=fact, resources='完整官方手册已下载；不是完整项目源码', fit='中' if ident=='I17' else '低', adapt='参考问题定义与项目闭环；具体行业适配详见候选选题文档', gap='历史获奖不代表适用第十一届技术要求，不能原样参赛'))
path.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding='utf-8')

groups = [('01_类似竞赛/腾讯云案例.md', ['腾讯云']), ('01_类似竞赛/华为云及其他竞赛案例.md', ['华为云','其他类似竞赛']), ('02_历届华为ICT/历届获奖作品.md', ['历届华为ICT'])]
for filename, selected in groups:
    rows = [c for c in cases if c['group'] in selected]
    text = ['# '+Path(filename).stem, '', '检索日期：2026-10-26。适配建议为本报告分析；奖项按对应赛事和阶段记录。没有源代码的案例不称为可复现项目。', '']
    for c in rows:
        text += ['## '+c['id']+' '+c['name'], '', '**赛事与奖项：** '+c['event']+'；'+c['award'], '', '**证据状态：** '+c['evidence'], '', '**公开内容：** '+c['fact'], '', '**可获取材料：** '+c['resources'], '', '**赛题三适配：** '+c['fit']+'。'+c['adapt'], '', '**限制：** '+c['gap'], '', '**来源：** '+c['source']+(('\n\n**作品/补充：** '+c['detail']) if c['detail'] else ''), '']
    target = ROOT / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('\n'.join(text), encoding='utf-8')

e = html.escape
rows = ''.join('<tr>'+''.join('<td>'+e(c[k])+'</td>' for k in ['id','group','name','event','award','fit'])+'<td>'+('<a href="'+e(c['source'],quote=True)+'">来源</a>' if c['source'].startswith('https') else e(c['source']))+'</td><td>'+e(c['evidence'])+'</td></tr>' for c in cases)
page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>ICT赛题三选题资料目录</title><style>body{font:15px/1.65 system-ui,sans-serif;color:#222;margin:24px;background:#fff}h1{font-size:25px}input{padding:10px;width:min(90%,620px);border:1px solid #888}table{border-collapse:collapse;width:100%;margin-top:20px}td,th{padding:9px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}th{background:#edf3ef}a{color:#12579c}.scroll{overflow:auto}td:nth-child(3){min-width:210px}td:nth-child(8){min-width:230px}</style><h1>华为ICT赛题三选题资料</h1><p>2026-10-26 · 分类案例、获奖作品与候选选题</p><p><a href="00_阅读导航.md">阅读导航与规则</a> · <a href="03_适配选题/候选选题与立项建议.md">12个候选选题</a> · <a href="04_技术与数据/技术资源与数据入口.md">技术与数据资源</a></p><label for="filter">筛选资料</label><br><input id="filter" type="search" placeholder="输入作品、行业、奖项或平台"><div class="scroll"><table><thead><tr><th>编号</th><th>分类</th><th>作品/线索</th><th>赛事</th><th>奖项</th><th>适配</th><th>来源</th><th>证据状态</th></tr></thead><tbody>'''+rows+'''</tbody></table></div><script>document.querySelector('#filter').addEventListener('input',e=>{const q=e.target.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))})</script></html>'''
(ROOT/'资料总索引.html').write_text(page, encoding='utf-8')

qa = ROOT/'05_来源核验/PDF预览'
qa.mkdir(exist_ok=True)
for pattern, numbers, prefix in [('*第十届*.pdf', [5,16,18], '华为手册'), ('*专项赛题.pdf',[27], '腾讯手册')]:
    pdf = pdfium.PdfDocument(str(next((ROOT/'04_技术与数据/已下载资料').glob(pattern))))
    for n in numbers:
        pdf[n].render(scale=1.2).to_pil().save(qa/(prefix+'_'+str(n+1)+'.png'))
    pdf.close()
print('Catalog entries:',len(cases))
print('Groups:', {g:sum(c['group']==g for c in cases) for g in sorted({c['group'] for c in cases})})
