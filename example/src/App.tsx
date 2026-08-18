// llms.txt가 안내한 CLI(`astryx component <Name> --dense`)로 확인한
// 실제 props로 작성한 "프로젝트 설정" 페이지.
// - Dialog: 저장 확인 모달 (isOpen/onOpenChange controlled, DialogHeader 필수 구성)
// - HoverCard: 작성자 이름에 호버하면 프로필 카드 (content + 트리거 children)
// `?demo=dialog` / `?demo=hovercard` 쿼리로 열면 해당 오버레이가 열린 상태로
// 시작한다 (스크린샷 검증용).
import {
  Avatar,
  Badge,
  Banner,
  Button,
  Card,
  DateInput,
  Dialog,
  DialogHeader,
  Divider,
  Heading,
  HoverCard,
  Stack,
  Switch,
  Text,
  TextArea,
  TextInput,
} from '@astryxdesign/core';
import type {ISODateString} from '@astryxdesign/core/Calendar';
import {useState} from 'react';

const demo = new URLSearchParams(window.location.search).get('demo');

function OwnerHoverCard() {
  return (
    <HoverCard
      label="작성자 프로필"
      placement="below"
      alignment="start"
      isDefaultOpen={demo === 'hovercard'}
      content={
        <Stack gap={2} padding={3} width={240}>
          <Stack direction="horizontal" gap={2} align="center">
            <Avatar name="Yuna Shan" size="md" tooltip={false} />
            <Stack gap={0.5}>
              <Text type="label">Yuna Shan</Text>
              <Text type="supporting">Design Engineer · in4ucloud</Text>
            </Stack>
          </Stack>
          <Divider />
          <Text type="supporting">이 프로젝트의 소유자입니다. 설정 변경 권한이 있습니다.</Text>
          <Button label="메시지 보내기" variant="secondary" size="sm" />
        </Stack>
      }>
      <Text type="supporting">@yuna</Text>
    </HoverCard>
  );
}

export default function App() {
  const [name, setName] = useState('Astryx Design Example');
  const [url, setUrl] = useState('https://example.dev');
  const [desc, setDesc] = useState('design.md와 llms.txt만 보고 만든 검증용 예제.');
  const [releaseDate, setReleaseDate] = useState<ISODateString | undefined>('2026-09-01');
  const [darkMode, setDarkMode] = useState(false);
  const [notify, setNotify] = useState(true);
  const [isSaveOpen, setIsSaveOpen] = useState(demo === 'dialog');
  const [isSaved, setIsSaved] = useState(false);

  return (
    <Stack align="center" paddingBlock={8}>
      <Stack gap={6} width="100%" maxWidth={720} paddingInline={4}>
        {isSaved ? (
          <Banner
            status="success"
            title="저장 완료"
            description="프로젝트 설정이 저장되었습니다."
            isDismissable
            onDismiss={() => setIsSaved(false)}
          />
        ) : (
          <Banner
            status="info"
            title="베타 안내"
            description="이 프로젝트는 현재 베타 상태입니다. 설정 변경은 즉시 적용됩니다."
          />
        )}

        <Stack direction="horizontal" gap={3} align="center">
          <Avatar name="Yuna Shan" size="lg" />
          <Stack gap={0.5}>
            <Heading level={1}>프로젝트 설정</Heading>
            <Stack direction="horizontal" gap={1} align="center">
              <Text type="supporting">astryx-design-example · 마지막 수정 오늘 ·</Text>
              <OwnerHoverCard />
            </Stack>
          </Stack>
          <Badge label="Active" variant="success" />
        </Stack>

        <Divider />

        <Stack gap={2}>
          <Heading level={2}>기본 정보</Heading>
          <Card>
            <Stack gap={4}>
              <TextInput label="프로젝트 이름" value={name} onChange={setName} />
              <TextInput
                label="공개 URL"
                description="배포 후 접근 가능한 주소입니다."
                value={url}
                onChange={setUrl}
              />
              <TextArea
                label="설명"
                description="프로젝트 목록에 표시되는 소개 문구입니다."
                value={desc}
                onChange={setDesc}
              />
              <DateInput
                label="출시 예정일"
                description="이 날짜에 프로젝트가 공개 상태로 전환됩니다."
                value={releaseDate}
                onChange={setReleaseDate}
                min="2026-08-18"
                isOptional
                hasClear
                width={280}
              />
            </Stack>
          </Card>
        </Stack>

        <Stack gap={2}>
          <Heading level={2}>환경 설정</Heading>
          <Card>
            <Stack gap={4}>
              <Switch
                label="다크 모드"
                description="시스템 설정과 무관하게 다크 테마를 강제합니다."
                value={darkMode}
                onChange={setDarkMode}
              />
              <Switch
                label="알림 받기"
                description="빌드 실패 시 이메일로 알립니다."
                value={notify}
                onChange={setNotify}
              />
            </Stack>
          </Card>
        </Stack>

        <Stack direction="horizontal" gap={2} justify="end">
          <Button label="취소" variant="secondary" />
          <Button label="변경 사항 저장" variant="primary" onClick={() => setIsSaveOpen(true)} />
        </Stack>
      </Stack>

      <Dialog isOpen={isSaveOpen} onOpenChange={setIsSaveOpen} purpose="info" width={400}>
        <DialogHeader
          title="변경 사항 저장"
          subtitle="아래 내용으로 프로젝트 설정을 갱신합니다."
          onOpenChange={setIsSaveOpen}
        />
        <Stack gap={3} paddingBlock={3}>
          <Text type="body">
            프로젝트 이름과 공개 URL은 즉시 반영되며, 배포 중인 환경에도 영향을 줍니다. 계속할까요?
          </Text>
          <Stack direction="horizontal" gap={2} justify="end">
            <Button label="취소" variant="ghost" onClick={() => setIsSaveOpen(false)} />
            <Button
              label="저장"
              variant="primary"
              onClick={() => {
                setIsSaveOpen(false);
                setIsSaved(true);
              }}
            />
          </Stack>
        </Stack>
      </Dialog>
    </Stack>
  );
}
