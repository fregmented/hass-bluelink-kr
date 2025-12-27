# 현대 블루링크 (대한민국) Home Assistant 통합

대한민국 현대 블루링크 계정을 Home Assistant에 연결하기 위한 커스텀 통합입니다. 현재는 기본 뼈대와 예시 센서만 포함되어 있으며, 실제 API 연동과 차량 상태 노출을 추가해 확장할 수 있습니다.

## 포함 구성요소

- `custom_components/bluelink_kr/manifest.json`: 통합 메타데이터.
- `custom_components/bluelink_kr/__init__.py`: 엔트리 설정, OAuth 토큰 관리/갱신, 데이터 업데이트 코디네이터.
- `custom_components/bluelink_kr/config_flow.py`: OAuth 클라이언트/로그인 플로우.
- `custom_components/bluelink_kr/sensor.py`: 예시 센서(계정 내 차량 수).
- `custom_components/bluelink_kr/const.py`: 공용 상수.
- `custom_components/bluelink_kr/strings.json` 및 `translations/*.json`: 설정 플로우 텍스트와 번역.

## 설치 방법

1. `custom_components/bluelink_kr` 폴더를 Home Assistant 설정 폴더의 `custom_components` 아래에 복사합니다.
2. Home Assistant를 재시작합니다.
3. 설정 → 기기 및 서비스 → 통합 추가에서 `Hyundai Bluelink (KR)`를 검색해 추가합니다.

## 설정 (OAuth)

- 설정 단계
  1) `Client ID`, `Client Secret`을 입력합니다.
  2) Home Assistant에 설정된 `external_url`을 redirect_uri로 사용해 블루링크 KR 로그인 페이지가 새 창/웹뷰로 열립니다.
  3) 리디렉션이 `external_url/api/bluelink_kr/oauth/callback`으로 돌아오면 Home Assistant가 코드(state 포함)를 자동 수신하고 설정을 완료합니다.
- 생성되는 엔트리 데이터
  - `client_id`, `client_secret`, `redirect_uri`, `authorization_code`, `state`, `authorize_url`
  - `access_token`, `refresh_token`, `token_type`, `access_token_expires_at`, `refresh_token_expires_at`, `user_id`
  - `terms_state`, `terms_user_id`, `terms_url` (데이터 공유 동의 과정)
  - `cars`, `car`, `selected_car_id` (차량 목록 및 선택)
- 첫 설정 후 예시 센서로 계정에 연결된 차량 수가 추가됩니다.
- 토큰 생명주기
  - 로그인 리다이렉트 후 `authorization_code`로 `access_token`/`refresh_token`을 발급받아 저장합니다.
  - `access_token`은 24시간마다 자동 갱신됩니다.
  - `refresh_token`은 365일 유효하며, 로그인 후 364일이 지나면 재인증 알림을 띄우고 재로그인 플로우를 시작합니다.
- 데이터 공유 동의
  - 토큰 발급 직후 현대 데이터 API 동의 창(terms agreement)을 새 창/웹뷰로 띄우며, state로 CSRF를 검증합니다.
  - 동의 완료 후 `terms_user_id`와 state가 콜백 엔드포인트(`/api/bluelink_kr/terms/callback`)로 반환됩니다. 실패 시 errCode/errMsg가 포함될 수 있습니다.
- 차량 선택/관리
  - 동의 완료 후 차량 목록을 조회해 사용자가 선택한 차량을 기기로 등록합니다(수정 불가).
  - 통합 옵션에서 “재검색”을 눌러 차량 목록을 다시 조회할 수 있으며, 닉네임 변경 시 기기 이름이 갱신되고 목록에 없는 차량은 비활성화됩니다.

## 현재 상태와 향후 작업

- 현재: 인증/통신 로직은 자리표시자이며, 예시 센서만 제공됩니다.
- 예정: 실제 현대 블루링크(대한민국) API 연동, 차량 상태/제어 엔티티 추가(센서, 이진 센서, 잠금, 위치 등), 오류 처리 및 재인증 로직 보강.

## 참고

이 통합은 실험적인 상태입니다. 실제 차량 데이터나 제어 기능을 추가할 때는 안전을 위해 충분한 테스트를 수행하세요.

## 라이선스

이 프로젝트는 BSD 3-Clause 라이선스를 따릅니다. 자세한 내용은 `LICENSE` 파일을 참고하세요.
