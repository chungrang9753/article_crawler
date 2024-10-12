from flask import Flask, render_template, request, redirect, send_file, url_for, session, flash, jsonify
import cx_Oracle
from openai import OpenAI
from dotenv import load_dotenv
import os
import FinanceDataReader as fdr
import pandas as pd
from io import BytesIO
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from bs4 import BeautifulSoup  # 추가
import re  # HTML 태그 제거를 위한 정규식
from pathlib import Path
import playsound
import sys
import subprocess
from datetime import datetime
import time
import matplotlib.pyplot as plt
from fpdf import FPDF
from pathlib import Path
import locale
import base64
from utils.report_utils import create_sibo_report
from flask import make_response
from flask import send_file
from io import BytesIO

# .env 파일 로드
load_dotenv('gpt.env')

# .env 파일에서 API 키를 가져옴
api_key = os.getenv('API_KEY')
client = OpenAI(api_key = api_key)

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # 세션을 위한 비밀 키 설정
# 오라클 DB 연결 설정
dsn = cx_Oracle.makedsn("172.30.1.16", "1521", service_name="XE")  # 이동욱 172.30.1.16
connection = cx_Oracle.connect(user="system", password="1234", dsn=dsn)

# Custom filter for comma-separated integers
def format_intcomma(value):
    return "{:,}".format(value)

def format_million(value):
    """백만 단위로 변환하고 소수점 두 자리까지 표시하는 필터"""
    value_in_millions = value / 1_000_000
    return "{:,.2f}".format(value_in_millions) + "M"

# 천 단위로 나누어주는 필터 정의
def format_thousands(value):
    """거래량을 천 단위로 나누어 표시"""
    return "{:,.0f}".format(value / 1000)

# 사용자 정의 필터 등록
app.jinja_env.filters['intcomma'] = format_intcomma
app.jinja_env.filters['million'] = format_million
app.jinja_env.filters['thousands'] = format_thousands

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        userid = request.form.get('userid')
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')

        # 비밀번호 암호화
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        cursor = None  # cursor 변수를 먼저 None으로 초기화
        # DB에 사용자 정보 저장
        try:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO users (userid, username, password, email) VALUES (:1, :2, :3, :4)",
                (userid, username, hashed_password, email)
            )
            connection.commit()
            flash('회원가입이 완료되었습니다! 로그인해 주세요.', 'success')
            return redirect(url_for('login'))
        except cx_Oracle.IntegrityError:
            flash('이미 존재하는 사용자 ID입니다.', 'danger')
        except cx_Oracle.DatabaseError as e:
            flash(f'에러 발생: {str(e)}', 'danger')
        finally:
            if cursor:  # cursor가 None이 아닌 경우에만 닫음
                cursor.close()
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        userid = request.form.get('userid')
        password = request.form.get('password')

        cursor = None  # cursor 변수를 먼저 None으로 초기화
        # DB에서 사용자 정보 조회
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT userid, username, password FROM users WHERE userid = :1", (userid,))
            user = cursor.fetchone()
            
            if user and check_password_hash(user[2], password):
                session['user_id'] = user[0]
                session['username'] = user[1]
                flash('로그인 성공!', 'success')
                return redirect(url_for('home'))
            else:
                flash('사용자 ID 또는 비밀번호가 올바르지 않습니다.', 'danger')
        except cx_Oracle.DatabaseError as e:
            flash(f'데이터베이스 오류: {str(e)}', 'danger')
        finally:
            if cursor:  # cursor가 None이 아닌 경우에만 닫음
                cursor.close()
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('home'))



@app.route('/')
def home():
    return render_template('home.html')

# KRX 상장 종목 리스트를 불러오는 함수
def load_allstock_KRX():
    krx_url = 'https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13'
    response = requests.get(krx_url)
    response.encoding = 'euc-kr'
    stk_data = pd.read_html(BytesIO(response.content), header=0)[0]
    stk_data = stk_data[['회사명', '종목코드']]
    stk_data = stk_data.rename(columns={'회사명': 'Name', '종목코드': 'Code'})
    stk_data['Code'] = stk_data['Code'].apply(lambda x: f'{x:06d}')
    return stk_data

# 특정 기업의 주가 정보를 조회하는 함수
def get_stock_price_by_name(company_name):
    stock_list = load_allstock_KRX()
    company_info = stock_list[stock_list['Name'] == company_name]
    if company_info.empty:
        return None, None, None
    stock_code = company_info.iloc[0]['Code']
    df_price = fdr.DataReader(stock_code).tail(5)  # 최근 5일간의 주가 데이터
    return company_info.iloc[0]['Name'], stock_code, df_price

def generate_stock_image_urls(stock_code):
    sidcode = str(int(time.time() * 1000))
    return {
        '1d': f"https://ssl.pstatic.net/imgfinance/chart/item/area/day/{stock_code}.png?sidcode={sidcode}",
        '3m': f"https://ssl.pstatic.net/imgfinance/chart/item/area/month3/{stock_code}.png?sidcode={sidcode}",
        '1y': f"https://ssl.pstatic.net/imgfinance/chart/item/area/year/{stock_code}.png?sidcode={sidcode}",
        '3y': f"https://ssl.pstatic.net/imgfinance/chart/item/area/year3/{stock_code}.png?sidcode={sidcode}",
    }

def get_kospi_image_url(period):
    if period == '1d':
        return "https://ssl.pstatic.net/imgstock/chart3/day/KOSPI.png?sidcode=1727155877867"
    elif period == '3m':
        return "https://ssl.pstatic.net/imgstock/chart3/day90/KOSPI.png?sidcode=1727155877867"
    elif period == '1y':
        return "https://ssl.pstatic.net/imgstock/chart3/day365/KOSPI.png?sidcode=1727155877867"
    elif period == '3y':
        return "https://ssl.pstatic.net/imgstock/chart3/day1095/KOSPI.png?sidcode=1727155877867"
    return None

def get_kospi_today_info():
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    
    kospi_today = fdr.DataReader('KS11', today, today)
    kospi_yesterday = fdr.DataReader('KS11', yesterday, yesterday)
    
    if kospi_today.empty or kospi_yesterday.empty:
        return None
    
    change_value = kospi_today['Close'].values[0] - kospi_yesterday['Close'].values[0]
    change_percent = (change_value / kospi_yesterday['Close'].values[0]) * 100
    
    kospi_info = {
        'current_price': kospi_today['Close'].values[0],
        'volume': kospi_today['Volume'].values[0],
        'trading_value': kospi_today['Close'].values[0] * kospi_today['Volume'].values[0],
        'high': kospi_today['High'].values[0],
        'low': kospi_today['Low'].values[0],
        'year_high': fdr.DataReader('KS11').max()['Close'],
        'year_low': fdr.DataReader('KS11').min()['Close'],
        'change_value': change_value,
        'change_percent': change_percent
    }
    
    return kospi_info

@app.route('/stock_info', methods=['GET', 'POST'])
def stock_info():
    company_name = request.form.get('company_name')
    period = request.form.get('period', '1d')
    stock_name, stock_code, stock_data = None, None, None
    stock_images = {}

    if company_name:
        stock_name, stock_code, stock_data = get_stock_price_by_name(company_name)
        if stock_code:
            stock_images = generate_stock_image_urls(stock_code)

    kospi_period = request.args.get('kospi_period', '1d')
    kospi_image = get_kospi_image_url(kospi_period)
    kospi_info = get_kospi_today_info()

    return render_template(
        'stock_info.html',
        company_name=stock_name,
        stock_code=stock_code,
        stock_data=stock_data,
        stock_images=stock_images,
        selected_period=period,
        kospi_image=kospi_image,
        kospi_info=kospi_info,
        kospi_period=kospi_period
    )
    
@app.route('/kospi_period', methods=['POST'])
def kospi_period():
    # POST 요청에서 선택된 기간 값을 받아옵니다. 기본값은 '1d'입니다.
    period = request.form.get('period', '1d')  
    # 선택된 기간에 맞는 KOSPI 지수 이미지를 가져옵니다.
    kospi_image = get_kospi_image_url(period)  
    # 현재 KOSPI 지수 정보를 가져옵니다.
    kospi_info = get_kospi_today_info()  
    
    # 페이지를 다시 렌더링하여 변경된 KOSPI 정보를 표시합니다.
    return render_template(
        'stock_info.html', 
        kospi_image=kospi_image, 
        kospi_info=kospi_info, 
        kospi_period=period
    )

@app.route('/search', methods=['GET', 'POST'])
def search():
    articles = []
    if request.method == 'POST':
        keyword = request.form.get('keyword')
        articles = fetch_latest_articles(keyword, 5)
    return render_template('search.html', articles=articles)

def fetch_latest_articles(keyword, count):
    """
    네이버 뉴스에서 키워드를 검색하여 최신 기사 5개를 가져오고 내용을 요약 및 감정 분석을 수행합니다.
    """
    base_url = "https://search.naver.com/search.naver"
    params = {
        'where': 'news',
        'query': keyword,
        'sort': '1'  # 최신순 정렬
    }
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(base_url, params=params, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')

    articles = []
    for idx, item in enumerate(soup.select('.news_wrap.api_ani_send'), start=1):
        if idx > count:  # 최신 기사 5개만 가져오기
            break

        title = item.select_one('.news_tit').get_text()
        link = item.select_one('.news_tit')['href']
        text = extract_summary(item.select_one('.dsc_txt_wrap').get_text())
        text = text.replace('요약: ', '')
        summary = text[0 : text.find('\n\n감정 분석: ')]
        print('summary =', summary)
        # sentiment = analyze_sentiment(summary)
        sentiment = text[text.find('감정 분석: '):]
        print('sentiment =', sentiment)

        # Save the article details to the database
        save_article_to_db(title, link, summary, sentiment, keyword)

        articles.append({
            "title": title,
            "link": link,
            "summary": summary,
            "sentiment": sentiment
        })

    return articles

def save_article_to_db(title, link, summary, sentiment, keyword):
    try:
        cursor = connection.cursor()
        query = "INSERT INTO news_summary (title, link, summary, sentiment, keyword) VALUES (:1, :2, :3, :4, :5)"
        cursor.execute(query, (title, link, summary, sentiment, keyword))
        connection.commit()
        cursor.close()
    except cx_Oracle.DatabaseError as e:
        print(f"Error saving article to database: {e}")

def extract_summary(text):
    """
    주어진 텍스트를 한국어로 요약합니다.
    """
    
    query = """
        뉴스 기사 본문 내용을 3줄 이내로 요약하고, 감정 분석을 하세요.

        예시 :
        
        1. 한화에어로스페이스, 방위산업 선도…K9 자주포·천무 등 유럽 수출
        한화그룹의 방위산업을 주도하고 있는 한화에어로스페이스는 한화디펜스에 이어 지난해 한화방산을 합병하며 몸집을 불렸다. 항공·우주·방산을 아우르는 기반을 확보, 수출시장 내 입지를 강화하고 해외 시장 공략에 나설 방침이다.
        한화에어로스페이스는 K9과 천무 등을 폴란드에 수출한 데 이어 지난 7월 에는 루마니아 국방부와 부쿠레슈티 현지에서 1조3828억원 규모의 자주포 등을 공급하는 계약을 맺었다. 현지 업체와 협력해 K9 자주포 54문과 K10 탄약 운반차 36대 등을 2027년부터 순차 납품할 예정이다.
        이번 계약에는 K9과 K10 외에도 정찰기상 관측용 차륜형 장비, 탄약 등 ‘자주포 패키지’가 포함됐다. 루마니아에 방산 토털 솔루션을 제시한 것이 최종 계약을 이끌었다는 평가다. 루마니아가 K9 10번째 운용 국가로 합류하면서 K9(K10 포함)의 누적 수출 총액은 13조원을 돌파했다. NATO 회원국 중 K9 자주포를 도입한 국가는 6개국까지 확대됐다. 예정된 계약 물량이 원활하게 수출되면 K9 점유율이 70%에 육박할 것이라는 관측도 나온다.
        수출시장 내 입지를 강화하기 위한 전략도 펼치고 있다. K9과 천무 등 수출 시장을 다변화하고, 자체 개발한 보병전투장갑차(IFV) 레드백으로 해외시장을 공략할 방침이다. ‘레드백’을 앞세워 호주 정부의 병 전투차량(IFV) 도입 사업에 선정되기도 했다. 한화에어로스페이스가 수출용으로 최초로 기획·개발한 무기체계인 레드백은 자주포와 장갑차 등 지상 장비 분야에서 축적한 기술로 개발됐다. 처음부터 수출을 목표로 상대국이 요구하는 사양을 이른 시일 내에 맞춰서 전략적으로 공급할 수 있는 수출 시스템을 만든 것이다.
        방산 분야의 무인화도 집중하고 있다. 다목적 무인 차량인 ‘아리온스멧’은 미국 국방부의 해외 비교성능시험 대상 장비로 선정 후 사업 계약을 체결했다. 작년 12월 초부터 3주간 미국 하와이 오아후 섬 해병대 훈련장에서 아리온스멧에 대한 본시험도 성공적으로 마쳤다.
        F-15K 전투기, T-50 고등훈련기 등 대한민국 공군의 주력 항공기 엔진과 한국형 헬기 ‘수리온’의 국산 엔진도 생산한다. 항공기 엔진 분야에서 독보적인 기술을 보유한 덕이다. 차세대한국형 전투기인 KF-21 ‘보라매’ 사업의 항공기 엔진 통합 개발을 주도적으로 수행한 바 있다. 제너럴일렉트릭(GE)와의 기술 협약을 통해 엔진 부품과 주요 부품의 국산화도 추진하고 있다.
        [감정분석 결과 : 긍정적]
        
        2. 와이즈넛, 거래소 예비심사 통과…코스닥 상장 채비 갖춰
        인공지능 전문기업 와이즈넛은 전날 한국거래소 코스닥시장 상장위원회의 심의∙의결을 거쳐 상장예비심사를 통과했다고 27일 밝혔다.
        와이즈넛은 증권신고서를 제출하고, 본격적인 공모 일정에 돌입할 계획이다. 상장 주관사는 삼성증권이 맡고 있다.
        앞서 지난 4월말 와이즈넛은 한국거래소에 예비심사 청구서를 제출한 바 있으며, 만 5개월만에 통과했다. 이는 올 초부터 한국거래소의 기술특례상장에 대한 심사 기준이 엄격해지며 보다 면밀한 심사가 이루어진 것으로 풀이된다.
        2000년 설립된 와이즈넛은 24년간 자체 개발해온 자연어처리기술 기반의 대용량 검색, AI 챗봇, 분석 등의 B2B사업을 위한 솔루션을 보유해왔다. 올 초부터 국내 최초 생성형AI 기반 RAG 솔루션을 활용한 다수의 사업과 연구과제에 착수해, 자체 LLM 개발과 함께 할루시네이션 등의 한계를 보완하고 의도에 부합하는 답변을 생성하는 AI 기술을 시장에 선보이고 있다.
        '자연어처리기술 기반의 대용량 검색과 AI챗봇' 두 분야의 탄탄한 핵심 사업을 중심으로 와이즈넛은 지난해 업계 최대 매출액 351억 7,200만원, 영업이익 34억 5,700만원, 당기순이익 42억 6,700만원을 기록했다. 전년 대비 매출은 2% 상승했고, 영업이익과 당기순이익은 각각 12%, 173% 증가한 수치다. 대내외 불확실성으로 인해 찬바람 부는 IT시장 속 11년 연속 영업이익 흑자 기조를 유지하고 있다.
        회사는 향후 상장을 통해 신규 자금을 확충하여, △AI 기술력 강화를 위한 연구개발 투자 확대 △생성형AI 기반 서비스 및 제품 포트폴리오 확장을 통한 신사업 확대 △글로벌 시장 진출을 위한 판로 개척 등에 적극 활용할 계획이다.
        와이즈넛 강용성 대표는 "코스닥 시장 상장의 첫 관문인 예비심사를 성공적으로 통과하게 됐다"며 "시장의 기대가 큰 만큼, 이어지는 증권신고서 제출과 앞으로의 상장 과정에 만전을 기해 성공적인 코스닥 상장을 이뤄내겠다"고 말했다.
        [감정분석 결과 : 긍정적]    
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "당신은 한국어로 요약을 도와주는 조수입니다."},
            {"role": "user", "content": f"뉴스 기사 본문 내용을 3줄 이내로 요약하고, 감정 분석을 하세요:\n\n{text}"}
        ],
        max_tokens=300,
        n=1,
        stop=None,
        temperature=0.0,
    )
    
    summary = response.choices[0].message.content.strip()
    return summary

# def analyze_sentiment(text):
#     """
#     주어진 텍스트의 정서를 한국어로 분석합니다.
#     """
    
#     # 1. '좋아해', '상승', '오른', '확대', '강세', '강력', '강화', '신제품', '공개', '거점으로 활용되며', '친환경', '생성', '지속 가능' 는 '긍정적' 으로
#         # '싫어해', '하락', '내린', '축소', '약세', '약화',  는 '부정적' 으로
#         # '~진행했다', '~발언했다', '~있다' 는 '중립적' 으로
#         # 위 부적적이거나 중립적이 아니면 '긍정적' 으로
#     query = """이것은 감성 분석 작업입니다.
#         다음 문장을 긍정적, 부정적, 중립적인 세 가지 감정 중 하나로 분류하십시오.

#         예:
#         '고용 줄었는데 인건비 늘었다',  는 '부정적' 으로
#         '더 절박함 가지고 노력' 는 '중립적' 으로
#         위 부적적이거나 중립적이 아니면 '긍정적' 으로

#         이제 이 문장을 분류하십시오. 분석할 문장은 아래와 같습니다:
#         '""" +text+ """'
#     """
#     print('query =', query)

#     response = client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[
#             {"role": "system", "content": query},
#             # {"role": "user", "content": f"다음 텍스트의 감정을 분석해 주세요:\n\n{text}\n\n감정 분석 결과:"}
#         ],
#         max_tokens=100,
#         # n=1,
#         # stop=None,  
#         # temperature=0.5,
#         temperature=0.0,
#         top_p=1,
#         frequency_penalty=0,
#         presence_penalty=0,
#         stop=["\n"]
#     )
    
#     sentiment = response.choices[0].message.content.strip()
#     return sentiment

@app.route('/chat', methods=['POST'])
def chat():
    """
    사용자가 챗봇에 질문을 하면 OpenAI API를 통해 응답을 반환합니다.
    """
    user_message = request.json.get('message', '')
    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 제공된 내용을 바탕으로 기사와 주가 정보에 대해 질문에 답하는 조수입니다."},
                {"role": "user", "content": user_message}
            ]
        )
        
        answer = response.choices[0].message.content.strip()
        return jsonify({"answer": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# TTS
@app.route('/tts', methods=['POST'])
def tts():
    fileName = 'speech.mp3'
    answer = request.json.get('answer', '')
    print('tts answer =', answer)
    
    if not answer:
        return jsonify({"error": "No answer provided"}), 400

    try:
        speech_file_path = Path(__file__).parent / fileName
        print('speech_file_path =', speech_file_path)
        
        speech = client.audio.speech.create(
            model="tts-1-hd",
            voice="nova", #alloy, echo, fable, onyx, nova, and shimmer
            input=answer
        )
        
        speech.write_to_file(speech_file_path)
        # playsound.playsound(fileName)
        process = subprocess.Popen([sys.executable, "-c", f"import playsound; playsound.playsound('{fileName}')"])
        
        # 오디오 재생이 끝날 때까지 기다림 (블로킹)
        process.wait()

        # 프로세스 종료 확인 (필요한 경우)
        if process.returncode == 0:
            print("오디오 재생 완료")
        else:
            print("오디오 재생 중 오류 발생")
            
        process.kill()
        return 'TRUE'
    except Exception as e:
        print('Exception =', e)
        return 'FALSE', 500

@app.route('/sibo')
def sibo():
    return render_template('sibo.html')

@app.route('/generate_report', methods=['POST'])
def generate_report():
    company_name = request.form.get('company_name')
    industry_name = request.form.get('industry_name')
    report_date = request.form.get('report_date')

    # 기사 및 감정 분석 데이터 가져오기
    company_articles = fetch_latest_articles(company_name, 5)
    industry_articles = fetch_latest_articles(industry_name, 5)

    # 주가 데이터 가져오기
    stock_name, stock_code, stock_data = get_stock_price_by_name(company_name)
    stock_images = generate_stock_image_urls(stock_code)

    # 보고서 생성
    pdf_buffer = create_sibo_report(
        company_name, 
        industry_name, 
        report_date, 
        company_articles, 
        industry_articles, 
        stock_images['1y'],  # 1년 차트 사용
        stock_data
    )

    # report_utils.py 파일 경로 가져오기
    report_utils_dir = os.path.dirname(os.path.abspath('report_utils.py'))
    report_folder = os.path.join(report_utils_dir, "report")
    os.makedirs(report_folder, exist_ok=True)

    file_path = os.path.join(report_folder, f"SIBO_Report_{company_name}_{report_date}.pdf")
    
    # PDF 파일 저장
    with open(file_path, 'wb') as f:
        f.write(pdf_buffer.getvalue())
    print(f"PDF 파일이 저장되었습니다: {file_path}")

    # PDF를 응답으로 보내기
    return send_file(
        BytesIO(pdf_buffer.getvalue()),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'SIBO_Report_{company_name}_{report_date}.pdf'
    )


# def fetch_and_analyze_articles(keyword, count):
#     articles = fetch_latest_articles(keyword, count)
#     for article in articles:
#         article['sentiment'] = analyze_sentiment(article['summary'])
#     return articles

def generate_stock_chart(stock_data):
    plt.figure(figsize=(8, 4))
    plt.plot(stock_data.index, stock_data['Close'])
    plt.title('Stock Price')
    plt.xlabel('Date')
    plt.ylabel('Price')
    plt.xticks(rotation=45)
    plt.tight_layout()

    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()

    graph = base64.b64encode(image_png)
    graph = graph.decode('utf-8')
    return graph

if __name__ == '__main__':
    app.run(debug=True)