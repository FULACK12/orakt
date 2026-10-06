"use strict";

(function createNewsI18n() {
  const dictionaries = {
    zh: {
      "nav.map": "事件地图",
      "nav.review": "聚类复核",
      "nav.research": "AI 研究报告",
      "nav.tasks": "实时任务台",
      "nav.docs": "API 文档",
      "status.local": "本地运行中",
      "language.switch": "EN",
      "language.label": "Switch to English",
    },
    en: {
      "nav.map": "Event map",
      "nav.review": "Cluster review",
      "nav.research": "AI research reports",
      "nav.tasks": "Task console",
      "nav.docs": "API docs",
      "status.local": "Running locally",
      "language.switch": "中文",
      "language.label": "切换到中文",
    },
  };
  let language = localStorage.getItem("newsapp-language") === "en"
    ? "en"
    : "zh";

  function register(bundle) {
    Object.assign(dictionaries.zh, bundle.zh || {});
    Object.assign(dictionaries.en, bundle.en || {});
  }

  function t(key, fallback = key) {
    return dictionaries[language][key] ?? fallback;
  }

  function apply(root = document) {
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
    root.querySelectorAll("[data-i18n]").forEach((element) => {
      element.textContent = t(element.dataset.i18n, element.textContent);
    });
    root.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
      element.placeholder = t(
        element.dataset.i18nPlaceholder,
        element.placeholder,
      );
    });
    root.querySelectorAll("[data-i18n-aria]").forEach((element) => {
      element.setAttribute(
        "aria-label",
        t(element.dataset.i18nAria, element.getAttribute("aria-label") || ""),
      );
    });
    const toggle = document.querySelector("#language-toggle");
    if (toggle) {
      toggle.textContent = t("language.switch");
      toggle.setAttribute("aria-label", t("language.label"));
    }
  }

  function setLanguage(nextLanguage) {
    language = nextLanguage === "en" ? "en" : "zh";
    localStorage.setItem("newsapp-language", language);
    apply();
    window.dispatchEvent(
      new CustomEvent("news:languagechange", {
        detail: { language },
      }),
    );
  }

  function initialize() {
    const toggle = document.querySelector("#language-toggle");
    if (toggle) {
      toggle.addEventListener("click", () => {
        setLanguage(language === "zh" ? "en" : "zh");
      });
    }
    apply();
  }

  window.NewsI18n = {
    apply,
    get language() {
      return language;
    },
    register,
    setLanguage,
    t,
  };
  document.addEventListener("DOMContentLoaded", initialize);
})();
