'use client';

import { createTheme } from '@mui/material/styles';

// System font stack (production should use next/font/google with Roboto)
// In restricted sandbox environments, Google Fonts may be unreachable
const fontFamily = [
  '"Inter"',
  '"Roboto"',
  '"Helvetica Neue"',
  'Arial',
  'sans-serif',
  '"Segoe UI"',
].join(',');

// VinUni Brand Colors per UI Style Guide
export const brandColors = {
  primary: '#0A2B57',     // VinUni Deep Navy
  accent: '#C72127',      // VinUni Signature Red
  active: '#941616',      // Burgundy / Deep Crimson
  secondary: '#134D8B',   // Secondary Navy
  interactive: '#2599DC', // Cyan Blue
};

export const statusColors = {
  // File status
  fileCompleted: { bg: '#ECFDF3', text: '#067647' },
  fileProcessing: { bg: '#EFF8FF', text: '#134D8B' },
  fileNeedsReview: { bg: '#FFFAEB', text: '#B54708' },
  fileError: { bg: '#FEF3F2', text: '#B42318' },

  // Matching status
  matchMeetsMandatory: { bg: '#E8F1FC', text: '#0A2B57' },
  matchNeedsVerification: { bg: '#FFFAEB', text: '#B54708' },
  matchPossibleMismatch: { bg: '#FDF2F2', text: '#941616' },

  // Application status
  appNew: { bg: '#F2F4F7', text: '#475467' },
  appInReview: { bg: '#EFF8FF', text: '#175CD3' },
  appShortlist: { bg: '#ECFDF3', text: '#067647' },
  appRejected: { bg: '#FEF3F2', text: '#B42318' },
};

const theme = createTheme({
  palette: {
    primary: {
      main: brandColors.primary,
      dark: '#071e3d',
      light: '#1e4d82',
    },
    secondary: {
      main: brandColors.accent,
      dark: brandColors.active,
      light: '#e53935',
    },
    info: {
      main: brandColors.interactive,
    },
    background: {
      default: '#F8FAFC',
      paper: '#FFFFFF',
    },
    text: {
      primary: '#112434',
      secondary: '#475569',
      disabled: '#A09F9C',
    },
    divider: '#E2E8F0',
  },
  typography: {
    fontFamily,
    h1: {
      fontSize: '28px',
      lineHeight: 1.29, // 36px
      fontWeight: 700,
    },
    h2: {
      fontSize: '22px',
      lineHeight: 1.27, // 28px
      fontWeight: 700,
    },
    h3: {
      fontSize: '18px',
      lineHeight: 1.33, // 24px
      fontWeight: 600,
    },
    h4: {
      fontSize: '15px',
      lineHeight: 1.47, // 22px
      fontWeight: 700,
    },
    body1: {
      fontSize: '14px',
      lineHeight: 1.43, // 20px
      fontWeight: 400,
    },
    body2: {
      fontSize: '14px',
      lineHeight: 1.43,
      fontWeight: 500,
    },
    caption: {
      fontSize: '12px',
      lineHeight: 1.33, // 16px
      fontWeight: 400,
      color: '#475569',
    },
    overline: {
      fontSize: '11px',
      lineHeight: 1.27, // 14px
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '0.5px',
    },
    button: {
      fontSize: '14px',
      fontWeight: 700,
      textTransform: 'none',
      borderRadius: 8,
    },
  },
  shape: {
    borderRadius: 8,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          padding: '10px 20px',
          boxShadow: 'none',
          '&:hover': {
            boxShadow: '0 2px 6px rgba(10, 43, 87, 0.25)',
          },
        },
        containedSecondary: {
          '&:hover': {
            backgroundColor: brandColors.primary,
          },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: 6,
            backgroundColor: '#FFFFFF',
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: {
          fontWeight: 600,
          color: '#112434',
          backgroundColor: '#F8FAFC',
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          '&:hover': {
            backgroundColor: '#F1F5F9',
          },
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: brandColors.primary,
          boxShadow: 'none',
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: brandColors.primary,
          color: '#FFFFFF',
        },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          '&.Mui-selected': {
            backgroundColor: brandColors.active,
            color: '#FFFFFF',
            '&:hover': {
              backgroundColor: '#7a1212',
            },
          },
          '&:hover': {
            backgroundColor: 'rgba(255,255,255,0.08)',
          },
        },
      },
    },
  },
});

export default theme;
