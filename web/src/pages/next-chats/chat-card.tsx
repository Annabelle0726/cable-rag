import { CardIdentityIcon } from '@/components/card-identity-icon';
import { HomeCard } from '@/components/home-card';
import { MoreButton } from '@/components/more-button';
import { useNavigatePage } from '@/hooks/logic-hooks/navigate-hooks';
import { IDialog } from '@/interfaces/database/chat';
import { ChatCardTrailing } from './chat-card-trailing';
import { ChatDropdown } from './chat-dropdown';
import { useRenameChat } from './hooks/use-rename-chat';

export type IProps = {
  data: IDialog;
} & Pick<ReturnType<typeof useRenameChat>, 'showChatRenameModal'>;

export function ChatCard({ data, showChatRenameModal }: IProps) {
  const { navigateToChat } = useNavigatePage();

  return (
    <HomeCard
      data={{
        name: data.name,
        description: data.description,
        update_time: data.update_time,
      }}
      leading={<CardIdentityIcon kind="chat" avatar={data.icon} />}
      trailing={<ChatCardTrailing messageCount={data.message_count} />}
      moreDropdown={
        <ChatDropdown chat={data} showChatRenameModal={showChatRenameModal}>
          <MoreButton></MoreButton>
        </ChatDropdown>
      }
      onClick={navigateToChat(data?.id)}
    />
  );
}
