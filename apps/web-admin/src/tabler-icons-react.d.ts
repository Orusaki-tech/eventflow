declare module "@tabler/icons-react" {
  import type React from "react";
  
  export interface IconProps extends React.SVGProps<SVGSVGElement> {
    size?: number | string;
    stroke?: number | string;
    strokeWidth?: number | string;
  }
  
  export const IconAlertTriangle: React.FC<IconProps>;
  export const IconArrowRight: React.FC<IconProps>;
  export const IconBuildingStore: React.FC<IconProps>;
  export const IconCalendarEvent: React.FC<IconProps>;
  export const IconCheck: React.FC<IconProps>;
  export const IconCircleCheck: React.FC<IconProps>;
  export const IconCircleX: React.FC<IconProps>;
  export const IconClock: React.FC<IconProps>;
  export const IconCoin: React.FC<IconProps>;
  export const IconDotsVertical: React.FC<IconProps>;
  export const IconHandStop: React.FC<IconProps>;
  export const IconLayoutDashboard: React.FC<IconProps>;
  export const IconLink: React.FC<IconProps>;
  export const IconLogout: React.FC<IconProps>;
  export const IconPhoto: React.FC<IconProps>;
  export const IconSettings: React.FC<IconProps>;
  export const IconShieldLock: React.FC<IconProps>;
  export const IconTicket: React.FC<IconProps>;
  export const IconVideo: React.FC<IconProps>;
  export const IconX: React.FC<IconProps>;
}
