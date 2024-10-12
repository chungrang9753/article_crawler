# article_crawler
키워드 관련 기사들을 웹 크롤링하여 가져오고 감정 분석, 요약하여 쉽게 파악할 수 있는 코드입니다.

# 주요 기능
* 입력한 키워드 관련 기사들을 웹 스크롤, 요약, 감정분석
  키워드 기반으로 네이버 뉴스에서 웹 크롤링을 사용하여 기사검색. gpt의 api key를 사용하여 요약 및 감정분석(긍정적이면 초록색, 중립이면 노란색, 부정적이면 주황색)
* 입력한 기업의 주가 정보와 코스피 지수 출력
* 레포트 출력
  날짜, 기업명, 산업명을 입력하고 버튼을 누르면 해당 날짜에 나온 기사들 중 기업, 산업과 관련된 기사들 중 긍정적, 부정적인 기사들을 각각 1개씩 출력합니다. 해당 날짜의 기업 주가정보까지 포함하여 레포트를 pdf로 작성하여 'report'폴더에 저장합니다.
* 챗 봇 기능
  기사를 찾고 나서 끼칠 영향이나 궁금한 사항을 검색하기 위해 화면의 우측하단에 챗 봇 기능을 구현하였습니다.
* TTS기능
  챗 봇에 질문을 작성하고 답변이 나오면 tts로 음성 출력됩니다.

# 설치 방법
기본 라이브러리 설치
### **pip install Flask cx_Oracle openai python-dotenv FinanceDataReader pandas requests**
### **pip install werkzeug beautifulsoup4 matplotlib fpdf playsound reportlab**

'gpt.env' 파일의 OPENAI_API_KEY에 gpt api key를 입력하셔야 챗 봇 기능과 뉴스 기사 요약 및 감정 분석 기능을 사용하실 수 있습니다.

Malgun 폰트를 사용, 폴더 지정 필요   
```C:/Windows/Fonts/malgun.ttf```   
```C:/Windows/Fonts/malgunbd.ttf```
