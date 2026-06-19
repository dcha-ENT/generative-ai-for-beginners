# korlp.org 게시글 추출기

대한이비인후과의사회([korlp.org](https://www.korlp.org)) 회원 전용 게시판 글을
**본인 회원 계정으로 로그인**한 세션에서 열어 본문을 추출하는 로컬 스크립트입니다.

로그인하지 않으면 `alert` 팝업이 뜨고 본문이 비어 나오는 페이지를 다루기 위해,
브라우저 다이얼로그를 가로채 메시지를 기록하고 로그인 폼 필드를 자동 감지합니다.

> ⚠️ 본인 회원 계정으로, 사이트 이용약관 범위 내에서만 사용하세요.
> 자동화 접근이 약관에 위배되지 않는지 먼저 확인하시기 바랍니다.

## 설치

```bash
cd tools/korlp-extractor
python -m venv .venv && source .venv/bin/activate   # 선택
pip install -r requirements.txt
playwright install chromium
```

## 설정

```bash
cp .env.example .env
# .env 를 열어 KORLP_ID, KORLP_PW 를 채웁니다.
```

`.env` 는 `.gitignore` 로 제외되어 커밋되지 않습니다. **계정 정보를 커밋하지 마세요.**

## 실행

```bash
# .env 의 KORLP_TARGET_URL 사용
python extract.py

# 또는 URL 직접 지정
python extract.py "https://www.korlp.org/html/?pmode=BBBS0028900025"
```

## 글이 안 열리고 홈으로 튕길 때 (가장 흔한 경우)

`?pmode=BBBS00289000XX` 처럼 **게시판 목록 주소**로 들어가면, 해당 게시판이
비활성화/권한제한된 경우 권한 거부 팝업이 뜨고 메인으로 리다이렉트됩니다.

개별 글은 **`seq` 번호가 붙은 주소**로 열어야 합니다:

```
?pmode=BBBS00289000XX&smode=view&seq=NNNNNN
```

본인 글의 정확한 주소(seq 포함)를 찾으려면 링크 수집 모드를 쓰세요:

```bash
# 마이페이지/내가 쓴 글 후보 페이지들을 돌며 개별 글 링크를 출력
python extract.py --links

# 특정 목록 페이지를 직접 지정
python extract.py --links "https://www.korlp.org/html/?pmode=my"
```

출력된 주소 중 원하는 글을 골라 그대로 추출하면 됩니다:

```bash
python extract.py "https://www.korlp.org/html/?pmode=BBBS0028900025&smode=view&seq=NNNNNN"
```

자동 수집이 안 되면, 브라우저에서 **마이페이지 → 내가 쓴 글**을 연 뒤
해당 글을 **우클릭 → 링크 주소 복사**해서 위 명령의 주소로 넣으세요.

## 출력

- 콘솔: 페이지 제목, 감지된 팝업 메시지, 추출된 본문
- `output/rendered.html` : 로그인 세션에서 렌더링된 전체 HTML
- `output/content.txt` : 추출된 본문 텍스트
- `output/screenshot.png` : 전체 페이지 스크린샷

## 로그인이 안 될 때

로그인 폼 필드 자동 감지가 실패하면 콘솔에 안내가 출력됩니다.

1. `KORLP_HEADLESS=false` 로 두고 실행해 브라우저 동작을 눈으로 확인합니다.
2. 브라우저 개발자도구(F12)로 ID/비밀번호 `input` 의 `name` 또는 `id` 를 확인합니다.
3. `.env` 에 셀렉터를 직접 지정합니다. 예:
   ```
   KORLP_ID_SELECTOR=input[name='mb_id']
   KORLP_PW_SELECTOR=input[type='password']
   KORLP_SUBMIT_SELECTOR=input[value='로그인']
   ```

## 주의

이 환경(원격 컨테이너)에는 브라우저가 설치되어 있지 않을 수 있으므로,
**로컬 PC에서 실행**하는 것을 전제로 작성되었습니다.
