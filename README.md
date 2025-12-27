# 현대 블루링크 (대한민국 국내용) Home Assistant 통합

## This integration uses APIs for internal use in Republic of Korea. It is not available for Hyundai vehicles sold outside of the Republic of Korea.

현대 블루링크 대한민국 계정을 Home Assistant에 연결하는 커스텀 통합입니다. OAuth 콜백을 HA 내부 HTTP 서버에서 처리하고, 선택한 차량의 주행/EV/경고 상태를 주기적으로 폴링합니다. 

## 현재 기능

- OAuth 로그인 후 차량 목록을 불러와 선택합니다. `external_url`을 기반으로 `/api/bluelink_kr/oauth/callback` 뷰를 등록합니다.
- 차량 기기 동기화: 선택한 차량을 장치 레지스트리에 등록하고 옵션 플로우의 “재검색”으로 목록을 다시 받아오며, 목록에 없어진 차량은 통합 비활성화 상태로 전환합니다.
- 엔티티
  - 센서: 주행가능거리, 누적 주행거리
  - EV/PHEV/FCEV 센서: EV SOC, 충전 중 여부, 충전 커넥터 연결, 플러그 타입, 목표 SOC, 충전 남은 시간(충전 중), 충전 예상 시간(미충전)
    - EV SOC/목표 SOC는 배터리 device_class 없이 일반 퍼센트 센서로 노출되어 통합 카드 상단 배터리 배지가 표시되지 않습니다.
  - 경고 센서: 연료/HV 배터리, 타이어 공기압, 램프, 스마트키 배터리, 워셔액, 브레이크 오일, 엔진 오일(비 EV)
  - 버튼: 강제 새로고침(모든 엔드포인트 순차 호출)
- 폴링 주기: 기본 코디네이터 5분 틱, 주행가능거리/주행거리/경고 60분, EV 배터리 5분, EV 충전 10분. 버튼으로 즉시 전체 새로고침 가능.

## 포함 구성요소

- `custom_components/bluelink_kr/manifest.json`: 통합 메타데이터.
- `custom_components/bluelink_kr/__init__.py`: 엔트리 설정, 토큰 관리/갱신, 데이터 업데이트 코디네이터, 강제 새로고침 처리.
- `custom_components/bluelink_kr/api.py`: OAuth/프로필/차량 목록, 주행가능거리·주행거리·EV 충전/배터리·경고 API 호출 래퍼.
- `custom_components/bluelink_kr/config_flow.py`: OAuth 클라이언트/로그인 플로우, 차량 선택 및 옵션 재검색.
- `custom_components/bluelink_kr/sensor.py`: 센서 엔티티 정의.
- `custom_components/bluelink_kr/button.py`: 강제 새로고침 버튼.
- `custom_components/bluelink_kr/device.py`: 선택 차량 기기 등록/비활성화 관리.
- `custom_components/bluelink_kr/views.py`: OAuth 통합 콜백 엔드포인트.
- `custom_components/bluelink_kr/strings.json` 및 `translations/*.json`: 설정 플로우 텍스트와 번역.

## 설치 방법

- HACS (권장)
  1. HACS → Integrations → 우상단 메뉴 → `Custom repositories`에서 `https://github.com/hanwoollee/hass-bluelink-kr`를 추가하고 Category를 `Integration`으로 선택합니다.
  2. HACS → Integrations에서 `현대 블루링크`를 설치합니다.
  3. Home Assistant를 재시작합니다.
- 직접 설치
  1. `custom_components/bluelink_kr` 폴더를 Home Assistant 설정 폴더의 `custom_components` 아래에 복사합니다.
  2. Home Assistant를 재시작합니다.
  3. 설정 → 기기 및 서비스 → 통합 추가에서 `현대 블루링크`를 검색해 추가합니다.

## 설정 (OAuth)

- 준비
  - Home Assistant `설정 → 시스템 → 네트워크`의 `외부 URL`이 설정돼 있어야 합니다.
  - Hyundai Developers에 가입합니다.(현대차 통합계정 또는 Pleos 계정 사용) 
  - 프로젝트를 생성합니다.
  - API 콘솔 -> 프로젝트 -> 내 차량 등록에서 등록할 차량을 활성으로 바꿉니다.
  - API 콘솔 -> 프로젝트 -> 설정에서 계정 API 리다이렉트 URL을 `https://{HASS_URL}/api/bluelink_kr/oauth/callback`으로 등록합니다.
- 단계
  1) `Client ID`, `Client Secret`을 입력합니다(`secrets.yaml`의 `bluelink_client_id`/`bluelink_client_secret` 값이 있으면 기본값으로 불러옵니다).
  2) Home Assistant가 설정한 `external_url`을 `redirect_uri`로 사용해 블루링크 KR 로그인 페이지가 새 창/웹뷰로 열립니다.
- 저장되는 데이터
  - 인증/서비스(`config_entries.data`): `client_id`, `client_secret`, `redirect_uri`, `access_token`, `refresh_token`, `token_type`, `access_token_expires_at`, `refresh_token_expires_at`, `user_id`
  - 차량/선택(`config_entries.options`): `cars`, `car`, `selected_car_id`
- 첫 설정 후 선택한 차량의 센서와 강제 새로고침 버튼이 추가됩니다.
- 차량 선택/관리
  - 로그인 후 차량 목록을 조회해 사용자가 선택한 차량을 기기로 등록합니다.
  - 통합 옵션의 “재검색” 버튼으로 차량 목록을 다시 조회해 닉네임 변경을 반영하고, 목록에 없는 차량을 비활성화합니다.

## 엔티티 목록

- 센서: Driving Range, Odometer
- EV/PHEV/FCEV 센서: EV SOC, Charging State, Charger Connection, Charging Plug Type, Charging Target SOC, Charging Time Remaining(충전 중), Charging Time Estimate(미충전)
- 경고 센서: Low Fuel/HV Battery Warning, Tire Pressure Warning, Lamp Warning, Smart Key Battery Warning, Washer Fluid Warning, Brake Fluid Warning, Engine Oil Warning(비 EV)
- 버튼: Force Refresh


## Lovelace 전용 카드

- 통합에 포함된 `bluelink-kr-card.js`를 자동으로 서빙·로드합니다. Home Assistant를 재시작한 뒤 Lovelace에서 `type: custom:bluelink-kr-card` 카드만 추가하면 됩니다.
- 구버전 HA로 인해 자동 로드가 동작하지 않는 경우에만 리소스를 수동 등록하세요: URL `/bluelink_kr/bluelink-kr-card.js`, 유형 `JavaScript Module`.
- Lovelace 시각 편집기에서 카드 유형 선택 후 각 센서 엔티티를 바로 지정할 수 있습니다(경고 센서는 필요한 만큼 추가).
- 예시 구성(`examples/lovelace/bluelink-kr-card.yaml`):

```yaml
type: custom:bluelink-kr-card
title: 아이오닉 6
show_warnings: true
entities:
  driving_range: sensor.ioniq6_driving_range
  odometer: sensor.ioniq6_odometer
  ev_soc: sensor.ioniq6_ev_soc
  charging_state: sensor.ioniq6_charging_state
  charger_connection: sensor.ioniq6_charger_connection
  charging_target_soc: sensor.ioniq6_charging_target_soc
  charging_time_remaining: sensor.ioniq6_charging_time_remaining
  charging_time_estimate: sensor.ioniq6_charging_time_estimate
  warnings:
    - sensor.ioniq6_low_fuel_warning
    - sensor.ioniq6_tire_pressure_warning
    - sensor.ioniq6_lamp_warning
    - sensor.ioniq6_smart_key_battery_warning
    - sensor.ioniq6_washer_fluid_warning
    - sensor.ioniq6_brake_fluid_warning
    - sensor.ioniq6_engine_oil_warning
```

- 옵션: `title`로 카드 상단 제목을 교체할 수 있으며, 경고 섹션을 숨기려면 `show_warnings: false`로 설정합니다. 경고 센서 목록은 차량 타입에 맞게 필요한 것만 포함하면 됩니다.

## 라이선스

이 프로젝트는 BSD 3-Clause 라이선스를 따릅니다. 자세한 내용은 `LICENSE` 파일을 참고하세요.
