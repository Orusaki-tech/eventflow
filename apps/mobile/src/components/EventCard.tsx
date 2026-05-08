import React from "react";
import { type ViewProps } from "react-native";
import { Card } from "../design/components/Card";

type Props = ViewProps & {
  children: React.ReactNode;
};

export function EventCard({ children, style, ...rest }: Props) {
  return (
    <Card style={[{ padding: 16, gap: 10 }, style]} {...rest}>
      {children}
    </Card>
  );
}

