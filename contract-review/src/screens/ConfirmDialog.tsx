import type { ReactNode } from 'react';
import { Dialog, DialogActions, DialogBody, DialogContent, DialogSurface, DialogTitle } from '@fluentui/react-components';
import { Btn } from './Btn';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  children: ReactNode;
}

export function ConfirmDialog({ open, title, confirmLabel, onConfirm, onCancel, children }: ConfirmDialogProps) {
  return (
    <Dialog
      open={open}
      onOpenChange={(_event, data) => {
        if (!data.open) onCancel();
      }}
    >
      <DialogSurface>
        <DialogBody>
          <DialogTitle>{title}</DialogTitle>
          <DialogContent>{children}</DialogContent>
          <DialogActions>
            <Btn variant="outline" onClick={onCancel}>
              Cancel
            </Btn>
            <Btn variant="cta" onClick={onConfirm}>
              {confirmLabel}
            </Btn>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}
