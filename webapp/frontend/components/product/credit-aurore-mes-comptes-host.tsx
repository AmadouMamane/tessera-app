"use client";

import {
  AlertTriangle,
  Bell,
  CalendarDays,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  CircleHelp,
  Facebook,
  FileSearch,
  Folder,
  Instagram,
  Mail,
  MapPin,
  MessageCircle,
  Power,
  Search,
  Settings,
  Share,
  ShieldCheck,
  Sprout,
  User,
  Users,
} from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";

import { PRODUCT_CHAT_EVENT } from "@/components/product/chat-widget";

const APPOINTMENT_PROMPT =
  "Je souhaite prendre rendez-vous avec un conseiller Crédit Aurore pour faire le point sur mes comptes.";
const GENERAL_HELP_PROMPT = "Bonjour, j'ai besoin d'aide sur mon espace client Crédit Aurore.";

function openProductChat(prompt?: string) {
  window.dispatchEvent(new CustomEvent(PRODUCT_CHAT_EVENT, { detail: { prompt } }));
}

const styles = `
  .ca-apercu3 {
    --ca-gold: #b99245;
    --ca-forest: #153f35;
    --ca-forest-dark: #071a17;
    --ca-ink: #050816;
    --ca-ivory: #f7f2e8;
    --ca-card: #fffdf7;
    --ca-page-bg: #efe7d8;
    --ca-card-border: #e4d8c4;
    --ca-line: #d7cbb8;
    --ca-text: #1e211c;
    --ca-muted: #665f51;
    height: 100vh;
    overflow-y: auto;
    background: #d9d2c4;
    color: var(--ca-text);
    font-family: Arial, Helvetica, "Helvetica Neue", sans-serif;
    font-synthesis-weight: none;
    -webkit-font-smoothing: antialiased;
  }

  .ca-apercu3 * {
    box-sizing: border-box;
  }

  .ca-apercu3 .portal-window {
    width: min(100%, 1718px);
    min-height: 100vh;
    margin: 0 auto;
    overflow: hidden;
    background: var(--ca-ivory);
  }

  .ca-apercu3 .util-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--ca-forest);
    color: var(--ca-ivory);
    font-size: 12px;
    font-weight: 700;
    padding: 8px 15px 7px;
  }

  .ca-apercu3 .util-bar span {
    display: inline-flex;
    align-items: center;
    gap: 7px;
  }

  .ca-apercu3 .util-bar svg {
    width: 15px;
    height: 15px;
  }

  .ca-apercu3 .main-head {
    display: flex;
    min-height: 69px;
    align-items: center;
    gap: 36px;
    border-bottom: 1px solid var(--ca-card-border);
    background: var(--ca-card);
    padding: 12px 23px 11px;
  }

  .ca-apercu3 .logo {
    display: flex;
    flex: none;
    align-items: center;
    gap: 9px;
    min-width: 250px;
  }

  .ca-apercu3 .brand-mark {
    display: block;
    width: 74px;
    height: 44px;
    flex: none;
    overflow: visible;
  }

  .ca-apercu3 .logo .txt {
    color: var(--ca-ink);
    line-height: 1.05;
  }

  .ca-apercu3 .logo .txt strong,
  .ca-apercu3 .logo .txt small {
    display: block;
  }

  .ca-apercu3 .logo .txt strong {
    font-size: 13.5px;
    font-weight: 850;
    letter-spacing: 0.45px;
  }

  .ca-apercu3 .logo .txt small {
    margin-top: 3px;
    color: #6f5c35;
    font-size: 9.5px;
    font-weight: 700;
    letter-spacing: 0.7px;
    text-transform: uppercase;
  }

  .ca-apercu3 .primary {
    display: flex;
    flex: 1;
    align-items: center;
    gap: 29px;
  }

  .ca-apercu3 .primary span {
    position: relative;
    color: #24302a;
    font-size: 13px;
    font-weight: 700;
    line-height: 1;
    white-space: nowrap;
  }

  .ca-apercu3 .primary .active {
    color: var(--ca-forest);
  }

  .ca-apercu3 .primary .active::after {
    position: absolute;
    right: 0;
    bottom: -25px;
    left: 0;
    height: 3px;
    background: var(--ca-forest);
    content: "";
  }

  .ca-apercu3 .head-icons {
    display: flex;
    flex: none;
    align-items: center;
    gap: 18px;
  }

  .ca-apercu3 .hi {
    position: relative;
    display: flex;
    min-width: 48px;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    color: var(--ca-ink);
    font-size: 10.5px;
    line-height: 1.1;
  }

  .ca-apercu3 .hi.search {
    min-width: 24px;
    margin-right: 5px;
  }

  .ca-apercu3 .hi svg {
    width: 22px;
    height: 22px;
    stroke-width: 1.8;
  }

  .ca-apercu3 .badge {
    position: absolute;
    top: -7px;
    right: 7px;
    display: flex;
    min-width: 15px;
    height: 15px;
    align-items: center;
    justify-content: center;
    border-radius: 999px;
    background: var(--ca-forest);
    color: var(--ca-ivory);
    font-size: 9px;
    font-weight: 800;
    padding: 0 4px;
  }

  .ca-apercu3 .power {
    display: flex;
    width: 30px;
    height: 30px;
    align-items: center;
    justify-content: center;
    border-radius: 999px;
    background: var(--ca-forest);
    color: var(--ca-ivory);
  }

  .ca-apercu3 .power svg {
    width: 17px;
    height: 17px;
  }

  .ca-apercu3 .subnav {
    display: flex;
    justify-content: flex-start;
    gap: 33px;
    border-bottom: 1px solid var(--ca-line);
    background: #f2eadc;
    padding: 9px 0 8px 139px;
  }

  .ca-apercu3 .subnav span {
    position: relative;
    color: #3a3f34;
    font-size: 13px;
    line-height: 1;
    white-space: nowrap;
  }

  .ca-apercu3 .subnav .active {
    color: var(--ca-forest);
    font-weight: 700;
  }

  .ca-apercu3 .subnav .active::after {
    position: absolute;
    right: 0;
    bottom: -11px;
    left: 0;
    height: 3px;
    background: var(--ca-forest);
    content: "";
  }

  .ca-apercu3 .page {
    background: var(--ca-page-bg);
    padding: 0 0 28px;
  }

  .ca-apercu3 h1,
  .ca-apercu3 h2,
  .ca-apercu3 h3,
  .ca-apercu3 h4 {
    margin: 0;
    color: var(--ca-ink);
    font-family: Arial, Helvetica, "Helvetica Neue", sans-serif;
    font-weight: 800;
    letter-spacing: 0;
  }

  .ca-apercu3 h1 {
    background: var(--ca-ivory);
    text-align: center;
    font-size: 40px;
    line-height: 1;
    padding: 36px 0 47px;
  }

  .ca-apercu3 .layout {
    display: grid;
    grid-template-columns: minmax(0, 818px) 377px;
    gap: 31px;
    max-width: 1274px;
    margin: 0 auto;
    padding: 54px 16px 24px;
  }

  .ca-apercu3 .sec-title {
    margin: 0 0 20px;
    color: var(--ca-ink);
    font-size: 22px;
    font-weight: 800;
    text-transform: uppercase;
  }

  .ca-apercu3 .col-left .sec-title:not(:first-child) {
    margin-top: 56px;
  }

  .ca-apercu3 .col-right .sec-title {
    margin-bottom: 41px;
    text-transform: none;
  }

  .ca-apercu3 .col-right {
    margin-top: -24px;
  }

  .ca-apercu3 .card,
  .ca-apercu3 .util-card {
    overflow: hidden;
    border: 1px solid var(--ca-card-border);
    border-radius: 4px;
    background: var(--ca-card);
    box-shadow: 0 2px 5px rgb(0 0 0 / 0.08);
  }

  .ca-apercu3 .acct-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 60px;
    padding: 0 16px;
  }

  .ca-apercu3 .acct-row + .acct-row {
    border-top: 1px solid var(--ca-line);
  }

  .ca-apercu3 .acct-left {
    display: flex;
    min-width: 0;
    align-items: center;
    gap: 24px;
  }

  .ca-apercu3 .acct-name {
    color: var(--ca-muted);
    font-size: 14px;
    font-weight: 800;
    white-space: nowrap;
  }

  .ca-apercu3 .acct-amt {
    color: var(--ca-ink);
    font-size: 20px;
    font-weight: 800;
    white-space: nowrap;
  }

  .ca-apercu3 .visa-card {
    position: relative;
    display: inline-block;
    width: 49px;
    height: 31px;
    flex: none;
    overflow: hidden;
    border-radius: 2px;
    background: linear-gradient(135deg, #efcf75, #d6ad4c 58%, #c49a35);
    box-shadow: 0 1px 2px rgb(0 0 0 / 0.28);
  }

  .ca-apercu3 .visa-card .stripe {
    position: absolute;
    top: 5px;
    left: 0;
    width: 9px;
    height: 20px;
    background: var(--ca-forest);
  }

  .ca-apercu3 .visa-card .chip {
    position: absolute;
    top: 8px;
    left: 10px;
    width: 8px;
    height: 6px;
    border-radius: 1px;
    background: #eed385;
  }

  .ca-apercu3 .visa-card::after {
    position: absolute;
    right: 5px;
    bottom: 4px;
    color: var(--ca-ivory);
    content: "VISA";
    font-size: 4px;
    font-weight: 800;
    letter-spacing: 0.3px;
  }

  .ca-apercu3 .badge-diff {
    margin-left: -6px;
    border: 1px solid var(--ca-forest);
    border-radius: 4px;
    color: var(--ca-forest);
    font-size: 10px;
    font-weight: 700;
    padding: 3px 8px;
  }

  .ca-apercu3 .save-card,
  .ca-apercu3 .cash-card {
    padding: 18px 16px 15px;
  }

  .ca-apercu3 .save-top,
  .ca-apercu3 .cash-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 13px;
  }

  .ca-apercu3 .progress {
    height: 8px;
    overflow: hidden;
    border-radius: 999px;
    background: #ded4c2;
  }

  .ca-apercu3 .progress i {
    display: block;
    height: 100%;
    background: #9c927f;
  }

  .ca-apercu3 .progress.green i {
    background: var(--ca-forest);
  }

  .ca-apercu3 .save-bottom {
    display: flex;
    justify-content: space-between;
    margin-top: 12px;
    color: var(--ca-muted);
    font-size: 14px;
  }

  .ca-apercu3 .cash-note {
    margin-top: 12px;
    color: var(--ca-muted);
    font-size: 14px;
    line-height: 1.5;
  }

  .ca-apercu3 .promo {
    overflow: hidden;
    margin-top: 31px;
    border: 1px solid var(--ca-card-border);
    background: var(--ca-card);
  }

  .ca-apercu3 .promo-main {
    display: flex;
    align-items: stretch;
    min-height: 151px;
  }

  .ca-apercu3 .promo .pic {
    position: relative;
    width: 160px;
    flex: none;
    overflow: hidden;
    background: linear-gradient(160deg, #dce9df, #f4e5c6 54%, #b99245);
  }

  .ca-apercu3 .promo .pic svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }

  .ca-apercu3 .promo .body {
    position: relative;
    flex: 1;
    padding: 9px 18px 10px 22px;
  }

  .ca-apercu3 .promo .tag {
    display: inline-block;
    border-radius: 4px;
    background: var(--ca-forest);
    color: var(--ca-ivory);
    font-size: 13px;
    font-weight: 800;
    padding: 6px 10px 7px;
    vertical-align: middle;
  }

  .ca-apercu3 .promo .tag sup {
    font-size: 8px;
  }

  .ca-apercu3 .promo .period {
    margin-left: 7px;
    color: var(--ca-ink);
    font-size: 12px;
    font-weight: 800;
    vertical-align: middle;
  }

  .ca-apercu3 .promo .mid {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-top: 7px;
  }

  .ca-apercu3 .promo .rate {
    display: flex;
    align-items: flex-start;
    gap: 4px;
    color: var(--ca-ink);
  }

  .ca-apercu3 .promo .rate .des {
    align-self: flex-start;
    padding-top: 5px;
    font-size: 14px;
    font-weight: 800;
  }

  .ca-apercu3 .promo .rate .num {
    font-size: 50px;
    font-weight: 800;
    line-height: 0.82;
  }

  .ca-apercu3 .promo .rate .pct {
    padding-top: 2px;
    font-size: 16px;
    font-weight: 800;
    line-height: 0.9;
  }

  .ca-apercu3 .promo h3 {
    color: var(--ca-ink);
    font-size: 22px;
    font-weight: 800;
    line-height: 1.05;
  }

  .ca-apercu3 .promo .desc {
    max-width: 435px;
    margin-top: 8px;
    color: #4a463d;
    font-size: 14px;
    line-height: 1.45;
  }

  .ca-apercu3 .promo .desc b {
    color: var(--ca-forest);
  }

  .ca-apercu3 .btn-primary {
    position: absolute;
    right: 25px;
    top: 97px;
    border: 0;
    border-radius: 20px;
    background: var(--ca-forest);
    color: var(--ca-ivory);
    cursor: default;
    font-size: 14px;
    font-weight: 800;
    padding: 11px 25px;
    white-space: nowrap;
  }

  .ca-apercu3 .promo .legal {
    background: #ded4c2;
    color: var(--ca-muted);
    font-size: 13px;
    line-height: 1.1;
    padding: 3px 8px;
  }

  .ca-apercu3 .util-card {
    margin-bottom: 38px;
    padding: 19px 16px 0;
  }

  .ca-apercu3 .util-card h4 {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
    color: var(--ca-ink);
    font-size: 17px;
    font-weight: 800;
  }

  .ca-apercu3 .util-card h4 svg {
    width: 19px;
    height: 19px;
  }

  .ca-apercu3 .util-link {
    display: flex;
    width: 100%;
    align-items: center;
    gap: 12px;
    min-height: 60px;
    border-top: 1px solid var(--ca-line);
    border-right: 0;
    border-bottom: 0;
    border-left: 0;
    background: transparent;
    color: #343a31;
    cursor: default;
    font-size: 15px;
    font: inherit;
    text-align: left;
  }

  .ca-apercu3 button.util-link {
    cursor: pointer;
  }

  .ca-apercu3 button.util-link:hover {
    color: var(--ca-forest);
  }

  .ca-apercu3 .util-link .ico {
    display: flex;
    width: 31px;
    justify-content: center;
    color: var(--ca-forest);
  }

  .ca-apercu3 .util-link svg {
    width: 28px;
    height: 28px;
    stroke-width: 1.8;
  }

  .ca-apercu3 footer {
    display: flex;
    align-items: center;
    gap: 82px;
    min-height: 110px;
    background: var(--ca-forest-dark);
    color: var(--ca-ivory);
    padding: 30px 211px;
  }

  .ca-apercu3 footer span {
    display: inline-flex;
    align-items: center;
    gap: 13px;
    color: var(--ca-ivory);
    font-size: 16px;
    font-weight: 700;
    white-space: nowrap;
  }

  .ca-apercu3 footer svg {
    width: 24px;
    height: 24px;
  }

  .ca-apercu3 footer .f-spacer {
    flex: 1;
  }

  .ca-apercu3 footer .socials {
    display: flex;
    align-items: center;
    gap: 27px;
  }

  .ca-apercu3 footer .socials svg {
    width: 30px;
    height: 30px;
  }

  .ca-apercu3 .side-widget {
    position: fixed;
    top: 50%;
    right: 0;
    z-index: 40;
    display: flex;
    flex-direction: column;
    gap: 19px;
    background: var(--ca-forest);
    box-shadow: 0 2px 6px rgb(0 0 0 / 0.2);
    padding: 18px 14px;
    transform: translateY(-50%);
  }

  .ca-apercu3 .side-widget .rail-action {
    display: flex;
    align-items: center;
    justify-content: center;
    border: 0;
    background: transparent;
    color: inherit;
    cursor: pointer;
    padding: 0;
  }

  .ca-apercu3 .side-widget .rail-action + .rail-action {
    border-top: 1px solid rgb(247 242 232 / 0.68);
    padding-top: 19px;
  }

  .ca-apercu3 .side-widget svg {
    width: 27px;
    height: 27px;
    color: var(--ca-ivory);
  }

  .ca-apercu3 .appointment-popover {
    position: fixed;
    top: 54%;
    right: 66px;
    bottom: auto;
    left: auto;
    z-index: 45;
    display: flex;
    width: 345px;
    flex-direction: column;
    align-items: center;
    border: 0;
    border-radius: 4px;
    background: var(--ca-forest);
    color: var(--ca-ivory);
    box-shadow: 0 16px 38px rgb(0 0 0 / 0.28);
    padding: 34px 42px 36px;
    margin: 0;
    text-align: center;
    transform: translateY(-50%);
  }

  .ca-apercu3 .appointment-close {
    position: absolute;
    top: 10px;
    right: 11px;
    display: flex;
    width: 24px;
    height: 24px;
    align-items: center;
    justify-content: center;
    border: 0;
    background: transparent;
    color: var(--ca-ivory);
    cursor: pointer;
    font-size: 25px;
    font-weight: 300;
    line-height: 1;
  }

  .ca-apercu3 .appointment-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--ca-ivory);
    margin-bottom: 10px;
  }

  .ca-apercu3 .appointment-icon svg {
    width: 66px;
    height: 66px;
    stroke-width: 1.8;
  }

  .ca-apercu3 .appointment-popover h3 {
    color: var(--ca-ivory);
    font-size: 23px;
    font-weight: 800;
    line-height: 1.15;
    margin: 0 0 20px;
  }

  .ca-apercu3 .appointment-popover p {
    color: var(--ca-ivory);
    font-size: 16px;
    font-weight: 800;
    line-height: 1.35;
    margin: 0 0 15px;
  }

  .ca-apercu3 .appointment-cta {
    width: 240px;
    min-height: 48px;
    border: 0;
    border-radius: 999px;
    background: var(--ca-gold);
    color: var(--ca-ink);
    cursor: pointer;
    font-size: 14px;
    font-weight: 800;
    margin-top: 1px;
    padding: 0 22px;
  }

  .ca-apercu3 .appointment-secondary {
    border: 0;
    background: transparent;
    color: var(--ca-ivory);
    cursor: pointer;
    font-size: 13px;
    font-weight: 800;
    margin-top: 30px;
    text-decoration: underline;
    text-underline-offset: 2px;
  }

  .ca-apercu3 .avis {
    position: fixed;
    right: 62px;
    bottom: 0;
    z-index: 40;
    display: flex;
    align-items: center;
    gap: 9px;
    border-radius: 4px 4px 0 0;
    background: var(--ca-forest);
    color: var(--ca-ivory);
    font-size: 14px;
    font-weight: 800;
    padding: 13px 18px;
  }

  .ca-apercu3 .avis svg {
    width: 17px;
    height: 17px;
  }

  @media (max-width: 1180px) {
    .ca-apercu3 .main-head {
      flex-wrap: wrap;
    }

    .ca-apercu3 .primary {
      order: 3;
      width: 100%;
      overflow-x: auto;
    }

    .ca-apercu3 .head-icons {
      margin-left: auto;
    }

    .ca-apercu3 .subnav {
      justify-content: flex-start;
      overflow-x: auto;
      padding-left: 24px;
      padding-right: 24px;
    }

    .ca-apercu3 .layout {
      grid-template-columns: minmax(0, 1fr);
      max-width: 860px;
    }

    .ca-apercu3 footer {
      padding: 28px 40px;
    }
  }

  @media (max-width: 760px) {
    .ca-apercu3 .util-bar {
      font-size: 11px;
      padding: 8px 12px;
    }

    .ca-apercu3 .util-bar span:first-child {
      max-width: 62%;
    }

    .ca-apercu3 .main-head {
      padding: 14px;
    }

    .ca-apercu3 .logo {
      gap: 8px;
      min-width: auto;
    }

    .ca-apercu3 .brand-mark {
      width: 64px;
      height: 38px;
    }

    .ca-apercu3 .logo .txt strong {
      font-size: 12px;
    }

    .ca-apercu3 .logo .txt small {
      font-size: 8px;
    }

    .ca-apercu3 .primary,
    .ca-apercu3 .head-icons {
      gap: 16px;
    }

    .ca-apercu3 .head-icons .hi:not(.search) {
      display: none;
    }

    .ca-apercu3 h1 {
      font-size: 34px;
      padding: 31px 0 34px;
    }

    .ca-apercu3 .layout {
      gap: 34px;
      padding-top: 38px;
    }

    .ca-apercu3 .sec-title {
      font-size: 19px;
    }

    .ca-apercu3 .acct-row,
    .ca-apercu3 .save-top,
    .ca-apercu3 .cash-top,
    .ca-apercu3 .save-bottom {
      align-items: flex-start;
      flex-direction: column;
      gap: 8px;
    }

    .ca-apercu3 .acct-left {
      flex-wrap: wrap;
      gap: 10px;
    }

    .ca-apercu3 .promo-main {
      flex-direction: column;
    }

    .ca-apercu3 .promo .pic {
      width: 100%;
      height: 150px;
    }

    .ca-apercu3 .promo .mid {
      align-items: flex-start;
      flex-direction: column;
    }

    .ca-apercu3 .btn-primary {
      position: static;
      margin-top: 14px;
    }

    .ca-apercu3 .side-widget {
      display: none;
    }

    .ca-apercu3 .appointment-popover {
      right: 16px;
      left: 16px;
      width: auto;
      padding: 30px 28px 34px;
    }

    .ca-apercu3 .avis {
      right: 16px;
    }

    .ca-apercu3 footer {
      align-items: flex-start;
      flex-direction: column;
      gap: 18px;
      padding: 28px 24px 76px;
    }

    .ca-apercu3 footer .f-spacer {
      display: none;
    }
  }
`;

/**
 * Fictional Crédit Aurore customer portal used only by `/produit/apercu3`.
 * The page is decorative, uses fictitious data, and bridges its CTAs to the
 * shared product chat instead of duplicating assistant logic.
 */
export function CreditAuroreMesComptesHost() {
  const [appointmentOpen, setAppointmentOpen] = useState(false);

  return (
    <div className="ca-apercu3">
      <style>{styles}</style>
      <div className="portal-window">
        <UtilityBar />
        <MainHeader />
        <SubNav />
        <main className="page">
          <h1>Mes comptes</h1>
          <div className="layout">
            <section className="col-left" aria-label="Comptes">
              <div className="sec-title">COMPTES BANCAIRES</div>
              <div className="card">
                <div className="acct-row">
                  <div className="acct-left">
                    <span className="acct-name">Compte Bancaire •••• 0260</span>
                  </div>
                  <span className="acct-amt">5 050,20 €</span>
                </div>
                <div className="acct-row">
                  <div className="acct-left">
                    <span className="visa-card" aria-hidden="true">
                      <span className="stripe" />
                      <span className="chip" />
                    </span>
                    <span className="acct-name">Carte Aurore Premier •••• 5857</span>
                    <span className="badge-diff">Débit différé</span>
                  </div>
                  <span className="acct-amt">-1 145,36 €</span>
                </div>
              </div>

              <div className="sec-title">COMPTES D'ÉPARGNE</div>
              <div className="card">
                <div className="save-card">
                  <div className="save-top">
                    <span className="acct-name">Livret A •••• 6687</span>
                    <span className="acct-amt">19,77 €</span>
                  </div>
                  <div className="progress" aria-hidden="true">
                    <i style={{ width: "0.6%" }} />
                  </div>
                  <div className="save-bottom">
                    <span>Utilisé: 0.1 %</span>
                    <span>Plafond de versements : 22 950,00 €</span>
                  </div>
                </div>
              </div>

              <div className="sec-title">CASHBACK</div>
              <div className="card">
                <div className="cash-card">
                  <div className="cash-top">
                    <span className="acct-name">Ma cagnotte</span>
                    <span className="acct-amt">28,15 €</span>
                  </div>
                  <div className="progress green" aria-hidden="true">
                    <i style={{ width: "100%" }} />
                  </div>
                  <div className="cash-note">
                    Remboursements en attente de validation : 0,00 €
                    <br />
                    Bonne nouvelle ! Votre cagnotte est disponible, vous pouvez l'encaisser dès
                    maintenant.
                  </div>
                </div>
              </div>

              <PromoBanner />
            </section>

            <UsefulLinks onOpenAppointment={() => setAppointmentOpen(true)} />
          </div>
        </main>
        <Footer />
      </div>
      <FloatingRail onOpenAppointment={() => setAppointmentOpen(true)} />
      {appointmentOpen && <AppointmentPopover onClose={() => setAppointmentOpen(false)} />}
    </div>
  );
}

function UtilityBar() {
  return (
    <div className="util-bar">
      <span>
        Espace clients professionnels Crédit Aurore
        <ChevronRight />
      </span>
      <span>
        <AlertTriangle />
        Aide et contacts
      </span>
    </div>
  );
}

function MainHeader() {
  return (
    <header className="main-head">
      <div className="logo" aria-label="Crédit Aurore">
        <CreditAuroreLogoMark />
        <span className="txt">
          <strong>CRÉDIT AURORE</strong>
          <small>Banque & assurance</small>
        </span>
      </div>
      <nav className="primary" aria-label="Navigation principale">
        <span className="active">Comptes et cartes</span>
        <span>Emprunter</span>
        <span>Épargner</span>
        <span>Assurer</span>
        <span>Nos conseils</span>
      </nav>
      <div className="head-icons" aria-hidden="true">
        <span className="hi search">
          <Search />
        </span>
        <span className="hi">
          <Bell />
          <span className="badge">1</span>
          <small>Notifications</small>
        </span>
        <span className="hi">
          <Mail />
          <span className="badge">40</span>
          <small>Messagerie</small>
        </span>
        <span className="hi">
          <Folder />
          <small>Documents</small>
        </span>
        <span className="hi">
          <User />
          <small>Profil</small>
        </span>
        <span className="power">
          <Power />
        </span>
      </div>
    </header>
  );
}

function CreditAuroreLogoMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 96 56" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="caLogoGreen" x1="4" x2="88" y1="4" y2="52">
          <stop offset="0" stopColor="#153f35" />
          <stop offset="1" stopColor="#071a17" />
        </linearGradient>
        <linearGradient id="caLogoGold" x1="45" x2="83" y1="7" y2="49">
          <stop offset="0" stopColor="#d6bd4e" />
          <stop offset="1" stopColor="#8b7722" />
        </linearGradient>
      </defs>
      <path
        d="M42.8 10.2C35.4 4.6 23.6 5.4 16.1 13.3 5.3 24.8 8.4 45.6 24.2 50.2c6.5 1.9 13.6.2 18.4-4.2"
        fill="none"
        stroke="url(#caLogoGreen)"
        strokeLinecap="round"
        strokeWidth="8.2"
      />
      <path
        d="M39.2 49.5 57.2 8.5 76 49.5"
        fill="none"
        stroke="url(#caLogoGold)"
        strokeLinejoin="miter"
        strokeWidth="7.6"
      />
      <path d="M48.6 34.3h17.9" stroke="#f3e4a8" strokeLinecap="round" strokeWidth="3.2" />
      <path
        d="M31.8 46.7C45.8 36.8 63.8 33.5 88 34.9"
        fill="none"
        stroke="url(#caLogoGreen)"
        strokeLinecap="round"
        strokeWidth="3.4"
      />
      <path
        d="M76.9 7.1 79.8 15.1 87.9 18 79.8 20.9 76.9 28.9 74 20.9 65.9 18 74 15.1z"
        fill="url(#caLogoGold)"
      />
      <path
        d="M76.9 10.4 78.5 16.4 84.5 18 78.5 19.6 76.9 25.6 75.3 19.6 69.3 18 75.3 16.4z"
        fill="#f6e7a7"
        opacity="0.72"
      />
    </svg>
  );
}

function SubNav() {
  return (
    <nav className="subnav" aria-label="Navigation comptes">
      <span className="active">Mes comptes</span>
      <span>Mes cartes</span>
      <span>Virements</span>
      <span>Prélèvements</span>
      <span>Mon budget</span>
      <span>Nos offres</span>
    </nav>
  );
}

function PromoBanner() {
  return (
    <div className="promo">
      <div className="promo-main">
        <div className="pic" aria-hidden="true">
          <svg viewBox="0 0 160 160" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
            <defs>
              <linearGradient id="caPromoSky" x1="0" x2="1" y1="0" y2="1">
                <stop offset="0" stopColor="#dce9df" />
                <stop offset="0.45" stopColor="#f7f2e8" />
                <stop offset="1" stopColor="#d1b36c" />
              </linearGradient>
              <linearGradient id="caPromoDress" x1="0" x2="1" y1="0" y2="1">
                <stop offset="0" stopColor="#fffdf7" />
                <stop offset="1" stopColor="#efe7d8" />
              </linearGradient>
            </defs>
            <rect width="160" height="160" fill="url(#caPromoSky)" />
            <circle cx="70" cy="57" r="23" fill="#202124" />
            <circle cx="104" cy="51" r="25" fill="#2a201c" />
            <circle cx="70" cy="65" r="14" fill="#c88962" />
            <circle cx="104" cy="62" r="14" fill="#b87852" />
            <path d="M38 160c9-45 27-67 52-66 24 1 40 24 45 66z" fill="url(#caPromoDress)" />
            <path d="M82 160c8-42 24-62 47-59 22 3 31 25 31 59z" fill="#efe7d8" />
            <path d="M40 112c18 11 43 14 67 2" fill="none" stroke="#9b6f32" strokeWidth="10" />
            <circle cx="66" cy="62" r="7" fill="#111" />
            <circle cx="99" cy="59" r="7" fill="#111" />
            <path d="M27 127c18-14 39-15 61-1" fill="none" stroke="#fffdf7" strokeWidth="7" />
          </svg>
        </div>
        <div className="body">
          <div>
            <span className="tag">
              PRÊT AURORE<sup>(1)</sup>
            </span>
            <span className="period">DU 08/06 AU 12/07/2026 INCLUS</span>
          </div>
          <div className="mid">
            <div className="rate">
              <span className="des">DÈS</span>
              <span className="num">5,99</span>
              <span className="pct">
                %<br />
                TAEG
                <br />
                FIXE
              </span>
            </div>
            <h3>Vos projets d'été commencent ici !</h3>
          </div>
          <p className="desc">
            Avec un prêt Aurore<sup>(1)</sup> d'un montant de 7 001 € à 50 000 € sur une durée de 48
            à 60 mois. <b>En plus, les frais de dossier sont offerts !</b>
          </p>
          <button className="btn-primary" type="button" tabIndex={-1}>
            Je découvre
          </button>
        </div>
      </div>
      <div className="legal">
        Un crédit vous engage et doit être remboursé. Vérifiez vos capacités de remboursement avant
        de vous engager.
      </div>
    </div>
  );
}

function UsefulLinks({ onOpenAppointment }: { onOpenAppointment: () => void }) {
  return (
    <aside className="col-right" aria-label="Liens utiles">
      <div className="sec-title">Liens utiles</div>
      <UtilCard
        title="Ma gestion"
        items={[
          { icon: <RibIcon />, label: "Télécharger mon RIB" },
          { icon: <FileSearch />, label: "Voir mes relevés" },
          { icon: <Settings />, label: "Personnaliser mes comptes" },
          { icon: <ShieldCheck />, label: "Sécurité Bancaire & Fraude" },
        ]}
      />
      <UtilCard
        title="Mes services"
        items={[
          { icon: <Users />, label: "Espace jeunes Aurore" },
          { icon: <Sprout />, label: "Bilan impact" },
          { icon: <Share />, label: "Gérer ma mobilité bancaire" },
          { icon: <Users />, label: "Parrainer mes proches" },
        ]}
      />
      <UtilCard
        title="Mes contacts"
        items={[
          {
            icon: <CalendarDays />,
            label: "Prendre rendez-vous",
            onClick: onOpenAppointment,
          },
          { icon: <AlertTriangle />, label: "Contacter les services d'urgence" },
        ]}
      />
    </aside>
  );
}

function UtilCard({
  title,
  items,
}: {
  title: string;
  items: { icon: ReactNode; label: string; onClick?: () => void }[];
}) {
  return (
    <section className="util-card">
      <h4>
        {title}
        <ChevronUp />
      </h4>
      {items.map((item) =>
        item.onClick ? (
          <button className="util-link" key={item.label} type="button" onClick={item.onClick}>
            <span className="ico">{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ) : (
          <div className="util-link" key={item.label}>
            <span className="ico">{item.icon}</span>
            <span>{item.label}</span>
          </div>
        ),
      )}
    </section>
  );
}

function RibIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <rect x="4" y="3" width="16" height="18" rx="2" />
      <text
        x="12"
        y="15"
        fill="currentColor"
        fontSize="7"
        fontWeight="700"
        stroke="none"
        textAnchor="middle"
      >
        RIB
      </text>
    </svg>
  );
}

function Footer() {
  return (
    <footer>
      <span>
        <MessageCircle />
        Questions fréquentes
      </span>
      <span>
        <MapPin />
        Trouver une agence
      </span>
      <span>
        Autres sites Crédit Aurore
        <ChevronDown />
      </span>
      <span className="f-spacer" />
      <div className="socials" aria-hidden="true">
        <Facebook />
        <Instagram />
        <XLogo />
      </div>
    </footer>
  );
}

function FloatingRail({ onOpenAppointment }: { onOpenAppointment: () => void }) {
  return (
    <>
      <div className="side-widget">
        <button
          className="rail-action"
          type="button"
          aria-label="Ouvrir l'assistant Crédit Aurore"
          onClick={() => openProductChat(GENERAL_HELP_PROMPT)}
        >
          <MessageCircle />
        </button>
        <button
          className="rail-action"
          type="button"
          aria-label="Prendre rendez-vous"
          onClick={onOpenAppointment}
        >
          <CalendarDays />
        </button>
      </div>
      <div className="avis" aria-hidden="true">
        <CircleHelp />
        Votre avis
      </div>
    </>
  );
}

function AppointmentPopover({ onClose }: { onClose: () => void }) {
  return (
    <dialog className="appointment-popover" open aria-labelledby="appointment-title">
      <button
        className="appointment-close"
        type="button"
        aria-label="Fermer le rendez-vous"
        onClick={onClose}
      >
        ×
      </button>
      <div className="appointment-icon" aria-hidden="true">
        <CalendarDays />
      </div>
      <h3 id="appointment-title">Prendre rendez-vous</h3>
      <p>Pour échanger dès aujourd'hui avec un conseiller par téléphone ou en agence.</p>
      <button
        className="appointment-cta"
        type="button"
        onClick={() => {
          onClose();
          openProductChat(APPOINTMENT_PROMPT);
        }}
      >
        Prendre rendez-vous
      </button>
      <button className="appointment-secondary" type="button" onClick={onClose}>
        Fermer
      </button>
    </dialog>
  );
}

function XLogo() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M18.9 2H22l-7.1 8.1L23.3 22h-6.6l-5.2-6.8L5.6 22H2.5l7.6-8.7L1.1 2h6.8l4.7 6.2L18.9 2zm-1.2 18h1.8L7.1 3.9H5.2L17.7 20z" />
    </svg>
  );
}
