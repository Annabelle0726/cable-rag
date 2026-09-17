import SvgIcon from '@/components/svg-icon';
import { useAuth } from '@/hooks/auth-hooks';
import {
  useLogin,
  useLoginChannels,
  useLoginWithChannel,
  useRegister,
} from '@/hooks/use-login-request';
import { useSystemConfig } from '@/hooks/use-system-request';
import { rsaPsw } from '@/utils';
import { useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import Spotlight from '@/components/spotlight';
import { Button, ButtonLoading } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm, UseFormReturn } from 'react-hook-form';
import { z } from 'zod';
import { NICKNAME_PATTERN } from '../user-setting/profile/constants';
import { BgSvg } from './bg';
import FlipCard3D, { FlipFaceContext } from './card';
import { LoginHero } from './hero';
import './index.less';

type LoginFormContentProps = {
  isLoginPage: boolean;
  title: string;
  form: UseFormReturn<any>;
  loading: boolean;
  onCheck: (params: any) => Promise<void>;
  changeTitle: () => void;
  registerEnabled: boolean;
  channels: { channel: string; icon?: string; display_name: string }[];
  handleLoginWithChannel: (channel: string) => void;
  t: ReturnType<typeof useTranslation>['t'];
  disablePasswordLogin?: boolean;
};

function LoginFormContent({
  isLoginPage,
  title,
  form,
  loading,
  onCheck,
  changeTitle,
  registerEnabled,
  channels,
  handleLoginWithChannel,
  t,
  disablePasswordLogin,
}: LoginFormContentProps) {
  const face = useContext(FlipFaceContext);
  const isActiveFace = isLoginPage ? face === 'front' : face === 'back';

  return (
    <div className="flex w-full flex-col items-center justify-center">
      <div className="mb-4 text-center">
        {/* The title carries the theme blue so it echoes the submit button
            rather than reading as plain black body copy. */}
        <h2 className="text-xl font-semibold text-accent-color">
          {title === 'login' ? t('loginTitle') : t('signUpTitle')}
        </h2>
      </div>
      {/* Glass card: a translucent pane over the page gradient with a hairline
          accent border, which lights up while a field inside it has focus. The
          padding stays tight because the register face carries one field more
          than the login face and both have to fit one screen. */}
      <div className="glass-panel w-full max-w-[440px] rounded-2xl px-6 py-5 transition-colors duration-200 ease-in-out focus-within:border-accent-color">
        {!disablePasswordLogin && (
          <Form {...form}>
            <form
              className="flex flex-col gap-4 text-text-primary"
              data-testid="auth-form"
              data-active={isActiveFace ? 'true' : undefined}
              onSubmit={form.handleSubmit(onCheck)}
            >
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel required>{t('emailLabel')}</FormLabel>
                    <FormControl>
                      <Input
                        data-testid="auth-email"
                        placeholder={t('emailPlaceholder')}
                        autoComplete="email"
                        className="focus-glow transition-colors duration-200 ease-in-out"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              {title === 'register' && (
                <FormField
                  control={form.control}
                  name="nickname"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel required>{t('nicknameLabel')}</FormLabel>
                      <FormControl>
                        <Input
                          data-testid="auth-nickname"
                          placeholder={t('nicknamePlaceholder')}
                          autoComplete="username"
                          className="focus-glow transition-colors duration-200 ease-in-out"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}

              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel required>{t('passwordLabel')}</FormLabel>
                    <FormControl>
                      <div className="relative">
                        <Input
                          data-testid="auth-password"
                          type={'password'}
                          placeholder={t('passwordPlaceholder')}
                          autoComplete={
                            title === 'login'
                              ? 'current-password'
                              : 'new-password'
                          }
                          className="focus-glow transition-colors duration-200 ease-in-out"
                          {...field}
                        />
                      </div>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {title === 'login' && (
                <FormField
                  control={form.control}
                  name="remember"
                  render={({ field }) => (
                    <FormItem>
                      <div className="flex gap-2 group">
                        <FormControl>
                          <Checkbox
                            checked={field.value}
                            onCheckedChange={(checked) => {
                              field.onChange(checked);
                            }}
                            className="group-hover:border-border-default group-hover:bg-border-button"
                          />
                        </FormControl>
                        <FormLabel
                          className={cn('cursor-pointer', {
                            'text-text-disabled': !field.value,
                            'text-text-primary': field.value,
                          })}
                        >
                          {t('rememberMe')}
                        </FormLabel>
                      </div>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}
              <ButtonLoading
                data-testid="auth-submit"
                type="submit"
                loading={loading}
                className="accent-gradient glow-accent my-1 w-full transition-colors duration-200 ease-in-out"
              >
                {title === 'login' ? t('login') : t('continue')}
              </ButtonLoading>
            </form>
          </Form>
        )}

        {title === 'login' && channels && channels.length > 0 && (
          <div
            className={cn(
              'space-y-2',
              !disablePasswordLogin && 'mt-4 border-t border-cable-border pt-4',
            )}
          >
            {channels.map((item) => (
              <Button
                variant={'outline'}
                key={item.channel}
                onClick={() => handleLoginWithChannel(item.channel)}
                className={cn(
                  'w-full gap-2 transition-colors duration-200 ease-in-out',
                  disablePasswordLogin && 'w-full',
                )}
              >
                <SvgIcon
                  name={item.icon || 'sso'}
                  width={20}
                  height={20}
                  imgClass="size-5"
                />
                Sign in with {item.display_name}
              </Button>
            ))}
          </div>
        )}

        {!disablePasswordLogin && title === 'login' && registerEnabled && (
          <div className="mt-4 text-center">
            <p className="text-text-secondary text-sm">
              {t('signInTip')}
              <Button
                data-testid="auth-toggle-register"
                variant={'transparent'}
                onClick={changeTitle}
                className="border-none font-medium text-accent-color transition-colors duration-200 hover:bg-transparent hover:text-accent-color-strong"
              >
                {t('signUp')}
              </Button>
            </p>
          </div>
        )}
        {!disablePasswordLogin && title === 'register' && (
          <div className="mt-4 text-center">
            <p className="text-text-secondary text-sm">
              {t('signUpTip')}
              <Button
                data-testid="auth-toggle-login"
                variant={'transparent'}
                onClick={changeTitle}
                className="border-none font-medium text-accent-color transition-colors duration-200 hover:bg-transparent hover:text-accent-color-strong"
              >
                {t('login')}
              </Button>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

const Login = () => {
  const [title, setTitle] = useState('login');
  const navigate = useNavigate();
  const { login, loading: signLoading } = useLogin();
  const { register, loading: registerLoading } = useRegister();
  const { channels, loading: channelsLoading } = useLoginChannels();
  const { login: loginWithChannel, loading: loginWithChannelLoading } =
    useLoginWithChannel();
  const { t } = useTranslation('translation', { keyPrefix: 'login' });
  const { t: tSetting } = useTranslation('translation', {
    keyPrefix: 'setting',
  });
  const { t: tHeader } = useTranslation('translation', {
    keyPrefix: 'header',
  });
  const [isLoginPage, setIsLoginPage] = useState(true);

  const loading =
    signLoading ||
    registerLoading ||
    channelsLoading ||
    loginWithChannelLoading;
  const { config } = useSystemConfig();
  const registerEnabled =
    config?.registerEnabled === 1 || config?.registerEnabled === true;

  const { isLogin } = useAuth();
  useEffect(() => {
    if (isLogin) {
      navigate('/');
    }
  }, [isLogin, navigate]);

  // The login route renders without the app shell (`layout: false`), so this
  // page owns the viewport: one screen, no scrollbars. The document is locked
  // while it is mounted, because the register face is taller than the login
  // face and must never turn the page itself into a scroll container.
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  const handleLoginWithChannel = async (channel: string) => {
    await loginWithChannel(channel);
  };

  const changeTitle = () => {
    setIsLoginPage(title !== 'login');
    if (title === 'login' && !registerEnabled) {
      return;
    }

    setTimeout(() => {
      setTitle(title === 'login' ? 'register' : 'login');
    }, 200);
  };

  const FormSchema = z
    .object({
      nickname: z.string().optional(),
      email: z
        .string()
        .email()
        .min(1, { message: t('emailPlaceholder') }),
      password: z.string().min(1, { message: t('passwordPlaceholder') }),
      remember: z.boolean().optional(),
    })
    .superRefine((data, ctx) => {
      if (title !== 'register') return;
      if (!data.nickname) {
        ctx.addIssue({
          path: ['nickname'],
          message: 'nicknamePlaceholder',
          code: z.ZodIssueCode.custom,
        });
        return;
      }
      if (!NICKNAME_PATTERN.test(data.nickname)) {
        ctx.addIssue({
          path: ['nickname'],
          message: tSetting('usernameInvalidCharacters'),
          code: z.ZodIssueCode.custom,
        });
      }
    });
  type FormValues = z.infer<typeof FormSchema>;
  const form = useForm<FormValues>({
    defaultValues: {
      nickname: '',
      email: '',
      password: '',
      remember: false,
    },
    resolver: zodResolver(FormSchema),
  });

  const onCheck = async (params: FormValues) => {
    try {
      const rsaPassWord = rsaPsw(params.password) as string;

      if (title === 'login') {
        const code = await login({
          email: `${params.email}`.trim(),
          password: rsaPassWord,
        });
        if (code === 0) {
          navigate('/');
        }
      } else {
        const code = await register({
          nickname: params.nickname ?? '',
          email: params.email,
          password: rsaPassWord,
        });
        if (code === 0) {
          setTitle('login');
        }
      }
    } catch (errorInfo) {
      console.log('Failed:', errorInfo);
    }
  };

  return (
    <>
      {/* The spotlight takes its colour from the theme's own default (white in
          dark mode, pale blue in light), so no colour is hard-coded here. */}
      <Spotlight opcity={0.4} coverage={60} />
      <Spotlight opcity={0.3} coverage={12} X={'10%'} Y={'-10%'} />
      <Spotlight opcity={0.3} coverage={12} X={'90%'} Y={'-10%'} />
      <div className="bg-cable-page relative flex h-screen w-screen items-center justify-center overflow-hidden">
        <BgSvg isPaused />

        {/* Two columns from `lg` up: the brand column on the left, the form on
            the right. Below `lg` the brand column is hidden and the form keeps
            the compact logo row instead, so the single-screen promise survives
            on a narrow window. */}
        <div className="relative z-10 grid h-full w-full max-w-[1180px] grid-cols-1 items-center gap-8 px-6 py-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,460px)] lg:gap-16">
          <LoginHero />

          <div className="flex w-full flex-col items-center">
            {/* Logo and product name read as one line, both on the same centre
                line. Only for narrow screens: the brand column above already
                names the product from `lg` up. */}
            <header className="mb-4 flex flex-row items-center justify-center gap-3 lg:hidden">
              <span className="glass-panel flex size-10 shrink-0 items-center justify-center rounded-xl">
                <SvgIcon name="brand-logo" width={24} height={24} />
              </span>
              <p className="text-xl font-semibold tracking-tight text-text-primary">
                {tHeader('brandShort')}
              </p>
            </header>

            {/* Login Form */}
            <FlipCard3D isLoginPage={isLoginPage}>
              <LoginFormContent
                isLoginPage={isLoginPage}
                title={title}
                form={form}
                loading={loading}
                onCheck={onCheck}
                changeTitle={changeTitle}
                registerEnabled={registerEnabled}
                channels={channels || []}
                handleLoginWithChannel={handleLoginWithChannel}
                t={t}
                disablePasswordLogin={!!config?.disablePasswordLogin}
              />
            </FlipCard3D>
          </div>
        </div>
      </div>
    </>
  );
};

export default Login;
