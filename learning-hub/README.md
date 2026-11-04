# 모아배움 — 학교·개인 통합 자료실

GitHub, Supabase, Netlify를 연결하는 **정적 웹앱**입니다. 기존 \`bolg\` 사이트의 \`public\` 콘텐츠는 변경하지 않고, 이 폴더를 **별도 Netlify 사이트**로 배포합니다.

## 현재 구현

- 학교/개인 공간 전환, 자료 유형·분류·검색·태그·정렬
- Google OAuth, 방문자용 Supabase 익명 세션 자동 로그인
- 관리자는 Google 계정 \`gim6110@gmail.com\`의 **검증된 Google 로그인**인 경우에만 판별
- Google 일반 사용자는 본인 자료만 수정·삭제. 게스트 게시물은 **게시물별 비밀번호**로 수정·삭제
- PDF 웹교과서: 페이지 이동, 확대, 검색(텍스트 PDF), 페이지별 개인 메모·책갈피·읽기 위치
- 링크, 외부 시뮬레이터 삽입(사이트 차단 시 별도 열기), 첨부파일 최대 50MB
- 즐겨찾기, 공유 링크, 관리자 다운로드 승인/반려, 모바일 반응형 UI

## 이번 계정에 실제 반영한 사항

- GitHub: \`gim6110-glitch/bolg/learning-hub/\`
- Supabase: \`izmumegfqvsorzkkixfi\`
- 데이터베이스에 \`schema.sql\`, \`security.sql\`, \`guest-flag.sql\` 순서로 마이그레이션 적용 완료
- 버킷 \`hub-private-files\` 생성. 기존 연수 등록부 프로젝트 \`jivkcfaidpgozouxvwhq\`는 변경하지 않음

## Netlify 배포 — 필수 1회 설정

1. Netlify에서 **Add new project → Import an existing project → GitHub**.
2. 저장소 **gim6110-glitch/bolg** 선택, 브랜치 **main**.
3. **Package directory = learning-hub**, **Base directory = 비워 두기**, **Publish directory = learning-hub**, **Build command = 비워 두기**.
4. 이 폴더의 \`netlify.toml\`이 우선 적용되었는지 배포 로그에서 확인합니다. 루트의 \`netlify.toml\`은 **기존 사이트용**이므로 변경하지 마세요.
5. 새 Netlify 사이트 도메인을 받은 후 아래 Supabase URL 설정에 추가합니다. 이후 GitHub에 수정사항을 올리면 자동 재배포됩니다.

설정 근거: https://docs.netlify.com/build/configure-builds/monorepos/

## Supabase 인증 — 필수 1회 설정

Supabase 프로젝트: https://supabase.com/dashboard/project/izmumegfqvsorzkkixfi

1. **Authentication → Sign In / Providers → Anonymous Sign-Ins**를 활성화합니다. 이 설정이 꺼져 있으면 게스트 자동 로그인과 자료 열람·게시가 정상 동작하지 않습니다.
2. 같은 화면에서 **Google** 공급자를 활성화하고, Google Cloud Console에서 발급한 OAuth Client ID와 Client Secret을 입력합니다.
3. Google OAuth의 **Authorized redirect URI**에는 다음 주소를 사용합니다.
   \`https://izmumegfqvsorzkkixfi.supabase.co/auth/v1/callback\`
4. **Authentication → URL Configuration**에서 Site URL을 새 Netlify 주소로 지정하고, Redirect URLs에도 \`https://새사이트.netlify.app/**\` 또는 연결할 사용자 지정 도메인 경로를 추가합니다.
5. 이메일 주소만 일치시켜 관리자 권한을 주지 않습니다. DB는 **확인된 Google 인증 identity가 있는 gim6110@gmail.com** 계정만 관리자라고 판별합니다. 테스트용 다른 Google 계정으로 관리자 기능이 나오지 않는지 확인하세요.

참고: https://supabase.com/docs/guides/auth/social-login/auth-google

## 사용법

- 방문자: 링크를 열면 게스트 세션 시작 → 게시 시 비밀번호(8자 이상) 설정 → 수정/삭제할 때 같은 비밀번호 사용.
- 다른 Google 사용자: Google 로그인 → 글·첨부자료 등록 → 자기 자료만 관리.
- 관리자: 지정된 Google 계정 로그인 → 상단 관리자 메뉴에서 다운로드 요청 승인 또는 반려 → 모든 게시물 수정·삭제.
- PDF 파일을 등록해 열면 웹교과서와 페이지 메모/책갈피가 나타납니다.
- 분류는 전공 분야/연수용 카테고리와 개인용 카테고리를 구분하여 제공합니다.

## 다운로드 권한의 기술적 한계

현재 구현은 **공식 파일 다운로드 버튼**에 관리자 승인 흐름을 적용합니다. PDF 웹 열람은 화면 렌더링을 위해 문서 바이트가 방문자의 브라우저에 전달되어야 하므로, PDF.js나 개발자 도구·캐시·스크린샷으로 파일 정보를 추출하는 행위를 완전히 막을 수 없습니다. 따라서 **강한 DRM이나 물리적 복사 방지 솔루션이 아닙니다**. 유출되면 안 되는 민감 자료나 학생 개인정보는 공개하지 마세요.

## 운영상 주의

- 게스트 비밀번호 분실 시 작성자 본인이 복구할 수 없습니다. 관리자는 글을 삭제할 수 있습니다.
- 게스트는 새 기기에서 게시물 비밀번호로 **본문 수정·삭제**가 가능합니다. 다만 기존 익명 세션이 아닌 경우 첨부파일 교체는 Storage 작성자 권한 때문에 제한될 수 있습니다.
- PDF 텍스트 검색은 OCR이 아닙니다. 스캔 이미지 PDF에는 검색이 작동하지 않을 수 있습니다.
- 외부 시뮬레이터를 iframe으로 불러오는 것은 원격 사이트의 X-Frame-Options/CSP 정책에 의해 차단될 수 있습니다. 이 경우 "연결 사이트 열기"를 사용합니다.
- 프론트엔드는 Supabase **publishable** 키만 포함하며 service role/secret key를 사용하지 않습니다.
- 공개 자료 열람과 다운로드 승인 사이에는 위에 설명한 기술적 한계가 있으므로 실제 강한 다운로드 통제가 필요하면 서버 측 렌더링, 워터마크 등 별도 정책을 설계해야 합니다.
- 브라우저 로그인과 Netlify 실제 배포는 Netlify/Google OAuth 설정 후 **운영 사이트에서 직접 검증**해야 합니다. 코드·DB 구축만으로 라이브 성공을 주장하지 않습니다.

## 검증 체크리스트

- [ ] 로그인하지 않은 새로운 브라우저에서 게스트 자동 입장
- [ ] 게스트가 비밀번호를 정해 글 등록, 다른 창에서 비밀번호 수정/삭제
- [ ] 일반 Google 계정은 다른 Google 작성자 글을 수정/삭제할 수 없음
- [ ] 관리자 Google 계정에서만 관리자 버튼 보임
- [ ] PDF 업로드·미리보기·페이지 메모·책갈피
- [ ] 다운로드 승인 요청/반려/승인에 따라 버튼 동작 변화
- [ ] 모바일 화면, 새로고침 및 공유 링크 복구
- [ ] Netlify GitHub 커밋 자동 반영

## 파일

- \`index.html\`: 반응형 웹앱 (ES modules, Supabase SDK, PDF.js)
- \`netlify.toml\`: 별도 Netlify 사이트용 설정
- \`schema.sql\`: 최초 Supabase 테이블/RLS/함수/Storage 구조
- \`security.sql\`: 비밀번호 해시 열 접근 제한
- \`guest-flag.sql\`: 안전한 게스트 게시물 표시 필드
