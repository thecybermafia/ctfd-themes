export function mergeObjects(target, source) {
  if (!target || typeof target !== "object") target = {};
  if (!source || typeof source !== "object") return target;

  for (const key of Object.keys(source)) {
    const sVal = source[key];
    if (Array.isArray(sVal)) {
      const targetArr = Array.isArray(target[key]) ? target[key] : [];
      target[key] = sVal.map((item, idx) => {
        if (item && typeof item === "object" && !Array.isArray(item)) {
          const base = (targetArr[idx] && typeof targetArr[idx] === "object") ? Object.assign({}, targetArr[idx]) : {};
          return mergeObjects(base, item);
        }
        return item;
      });
    } else if (sVal && typeof sVal === "object") {
      target[key] = mergeObjects(target[key] && typeof target[key] === "object" ? target[key] : {}, sVal);
    } else {
      target[key] = sVal;
    }
  }
  return target;
}
