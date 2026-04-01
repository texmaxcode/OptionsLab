(function () {
  var path = window.location.pathname.replace(/\/$/, "").split("/").pop() || "index.html";
  if (!path.includes(".html")) path = "index.html";

  document.querySelectorAll("nav#sidebar > a[href]").forEach(function (a) {
    var h = a.getAttribute("href");
    if (!h || h.startsWith("#")) return;
    var hFile = h.split("/").pop() || h;
    if (hFile === path) a.classList.add("active");
  });
  var sec = document.querySelectorAll("main section[id]");
  var links = document.querySelectorAll('nav#sidebar a[href^="#"]');
  if (sec.length < 2 || links.length < 2) return;
  function onScroll() {
    var id = "";
    sec.forEach(function (s) {
      if (window.scrollY >= s.offsetTop - 120) id = s.id;
    });
    links.forEach(function (l) {
      l.classList.toggle("active", l.getAttribute("href") === "#" + id);
    });
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
})();
