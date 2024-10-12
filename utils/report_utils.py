from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.units import inch
from datetime import datetime
import os
from io import BytesIO
from textwrap import wrap

# 폰트 등록
pdfmetrics.registerFont(TTFont('Malgun', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('Malgun-Bold', 'C:/Windows/Fonts/malgunbd.ttf'))

def create_sibo_report(company_name, industry_name, report_date, company_articles, industry_articles, stock_chart_url, stock_data):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    draw_page(c, width, height, company_name, industry_name, report_date, company_articles, industry_articles, stock_chart_url, stock_data)

    c.save()
    buffer.seek(0)
    return buffer

def draw_section_header(c, y_position, section_title):
    # 소제목을 주황색 박스 안에 흰색 글씨로 표현
    c.setFillColor(colors.orange)
    c.rect(100, y_position - 15, 170, 25, fill=1)  # (x, y, 너비, 높이)

    c.setFillColor(colors.white)
    c.setFont("Malgun-Bold", 14)
    c.drawString(110, y_position - 10, section_title)

    c.setFillColor(colors.black)
    return y_position - 35  # 다음 섹션을 위해 위치 조정

def draw_page(c, width, height, company_name, industry_name, report_date, company_articles, industry_articles, stock_chart_url, stock_data):
    # 제목 (가운데 정렬)
    c.setFont("Malgun-Bold", 24)
    title = "SIBO Daily Report"
    title_width = pdfmetrics.stringWidth(title, "Malgun-Bold", 24)
    title_x = (width - title_width) / 2
    c.drawString(title_x, height - 50, title)

    # 날짜 (오른쪽 상단)
    c.setFont("Malgun", 12)
    c.drawString(width - 150, height - 50, report_date)

    # 기업명 및 산업명 포함한 보고서 부제 (가운데 정렬)
    sub_title = f"- {company_name} {industry_name} 언론 모니터링 보고서 -"
    sub_title_width = pdfmetrics.stringWidth(sub_title, "Malgun", 14)
    sub_title_x = (width - sub_title_width) / 2
    c.setFont("Malgun", 14)
    c.drawString(sub_title_x, height - 80, sub_title)

    y_position = height - 110

    # 여론동향(대외이미지) 섹션 헤더
    y_position = draw_section_header(c, y_position, "여론동향(대외이미지)")

    # 감정 분석 결과
    positive = sum(1 for article in company_articles if '긍정적' in article['sentiment'])
    neutral = sum(1 for article in company_articles if '중립적' in article['sentiment'])
    negative = sum(1 for article in company_articles if '부정적' in article['sentiment'])

    c.setFont("Malgun", 12)
    c.drawString(100, y_position, f"긍정 기사: {positive}개, 중립 기사: {neutral}개, 부정 기사: {negative}개")
    y_position -= 20

    max_sentiment = max(positive, neutral, negative)
    c.setFont("Malgun-Bold", 12)
    if max_sentiment == positive:
        c.drawString(100, y_position, "긍정적인 기사가 가장 많습니다.")
    elif max_sentiment == neutral:
        c.drawString(100, y_position, "중립적인 기사가 가장 많습니다.")
    else:
        c.drawString(100, y_position, "부정적인 기사가 가장 많습니다.")
    y_position -= 30

    # 기업 관련 기사 (소제목 주황색 박스)
    y_position = draw_section_header(c, y_position, f"{company_name} 관련 기사")

    positive_article = next((article for article in company_articles if '긍정적' in article['sentiment']), None)
    negative_article = next((article for article in company_articles if '부정적' in article['sentiment']), None)

    if positive_article:
        y_position = draw_article(c, positive_article, y_position, width, True)
    if negative_article:
        y_position = draw_article(c, negative_article, y_position, width, False)

    # 산업 관련 기사 (소제목 주황색 박스)
    y_position = draw_section_header(c, y_position, f"{industry_name} 관련 기사")

    positive_industry_article = next((article for article in industry_articles if '긍정적' in article['sentiment']), None)
    negative_industry_article = next((article for article in industry_articles if '부정적' in article['sentiment']), None)

    if positive_industry_article:
        y_position = draw_article(c, positive_industry_article, y_position, width, True)
    if negative_industry_article:
        y_position = draw_article(c, negative_industry_article, y_position, width, False)

    # 주가 정보 (소제목 주황색 박스)
    y_position = draw_section_header(c, y_position, "주가 정보")

    # 주가 그래프 (크기를 1.5배로 늘림)
    if stock_chart_url:
        c.drawImage(stock_chart_url, 100, y_position - 112, width=225, height=112)
    else:
        c.drawString(100, y_position, "차트 이미지를 불러올 수 없습니다.")

    # 주가 데이터 표 (위치 조정)
    data = [['날짜', '시가', '고가', '저가', '종가', '거래량']]
    for date, row in stock_data.iterrows():
        data.append([date.strftime('%Y-%m-%d'), row['Open'], row['High'], row['Low'], row['Close'], row['Volume']])

    table = Table(data, colWidths=[0.53*inch, 0.47*inch, 0.47*inch, 0.47*inch, 0.47*inch, 0.6*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Malgun-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Malgun'),
        ('FONTSIZE', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    table.wrapOn(c, width, height)
    table.drawOn(c, 335, y_position - 112)  # 차트 오른쪽에 표 위치 조정

def draw_article(c, article, y_position, width, is_positive):
    # 감정 표시 동그라미
    c.setFillColor(colors.green if is_positive else colors.red)
    c.circle(110, y_position + 5, 5, fill=1)
    c.setFillColor(colors.black)

    c.setFont("Malgun-Bold", 12)
    title_lines = wrap(article['title'], width=55)  # 55글자마다 줄바꿈
    for line in title_lines:
        c.drawString(120, y_position, line)
        y_position -= 15

    c.setFont("Malgun", 10)
    summary = article['summary'][:150] + "..." if len(article['summary']) > 150 else article['summary']
    wrapped_summary = wrap(summary, width=55)  # 55글자마다 줄바꿈
    for line in wrapped_summary:
        c.drawString(120, y_position, line)
        y_position -= 15

    c.drawString(120, y_position, f"감정 분석: {article['sentiment']}")
    y_position -= 15

    # URL 출력 시 글자 크기를 7로 조정
    c.setFont("Malgun", 7)
    url_lines = wrap(article['link'], width=80)
    for line in url_lines:
        c.drawString(120, y_position, f"URL: {line}")
        y_position -= 10

    # 글자 크기 복원
    c.setFont("Malgun", 10)
    y_position -= 15
    return y_position
